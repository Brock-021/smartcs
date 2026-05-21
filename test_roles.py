#!/usr/bin/env python3
"""SmartCS 三员管理 — 角色权限集成测试"""
import urllib.request, urllib.error, json, http.cookiejar, sys, os, traceback

BASE = os.environ.get('TEST_BASE', 'http://localhost:5000')
PASS = 0; FAIL = 0
def test(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f'  ✅ {name}')
    else:
        FAIL += 1
        print(f'  ❌ {name}' + (f' — {detail}' if detail else ''))

class RoleTester:
    def __init__(self):
        self.opener = None

    def login(self, email, password):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        data = json.dumps({'email': email, 'password': password}).encode()
        req = urllib.request.Request(f'{BASE}/agent/login', data=data,
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            resp = opener.open(req, timeout=10)
            d = json.loads(resp.read())
            self.opener = opener
            return d
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read())
            except: return None

    def get(self, path):
        try:
            resp = self.opener.open(urllib.request.Request(f'{BASE}{path}'), timeout=10)
            ct = resp.headers.get('Content-Type', '')
            raw = resp.read()
            if 'json' in ct: return json.loads(raw)
            return raw.decode()
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read())
            except: return {'_status': e.code}
        except: return None

    def post(self, path, data=None):
        body = json.dumps(data).encode() if data else None
        try:
            resp = self.opener.open(urllib.request.Request(f'{BASE}{path}', data=body,
                headers={'Content-Type': 'application/json'}), timeout=10)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read())
            except: return {'_status': e.code}
        except Exception as e:
            return {'_error': str(e)}

    def delete(self, path):
        try:
            resp = self.opener.open(urllib.request.Request(f'{BASE}{path}', method='DELETE',
                headers={'Content-Type': 'application/json'}), timeout=10)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read())
            except: return {'_status': e.code}
        except Exception as e:
            return {'_error': str(e)}

def run_tests():
    t = RoleTester()
    print('=' * 60)
    print('  SmartCS 三员管理 — 角色权限集成测试')
    print(f'  Server: {BASE}')
    print('=' * 60)

    # ---- 1. 登录测试 ----
    print('\n📋 1. 登录测试')
    r = t.login('sysadmin@smartcs.com', 'SysAdmin@2026')
    test('sysadmin 登录成功', r and r.get('role') == 'sysadmin', str(r))
    r = t.login('secadmin@smartcs.com', 'SecAdmin@2026')
    test('secadmin 登录成功', r and r.get('role') == 'secadmin', str(r))
    r = t.login('audadmin@smartcs.com', 'AudAdmin@2026')
    test('audadmin 登录成功', r and r.get('role') == 'audadmin', str(r))
    r = t.login('admin@smartcs.com', 'admin123')
    test('superadmin 登录成功', r and r.get('role') == 'superadmin', str(r))

    # ---- 2. sysadmin 权限边界 ----
    print('\n📋 2. Sysadmin 权限边界')
    t.login('sysadmin@smartcs.com', 'SysAdmin@2026')
    r = t.get('/api/admin/audit-logs')
    test('sysadmin 不能查看审计日志', isinstance(r, dict) and 'error' in r, str(r))
    r = t.get('/api/admin/login-logs')
    test('sysadmin 不能查看登录日志', isinstance(r, dict) and 'error' in r, str(r))
    r = t.get('/api/admin/security-config')
    test('sysadmin 不能访问安全配置', isinstance(r, dict) and 'error' in r, str(r))
    r = t.post('/api/admin/auth-providers', {'name':'test','provider_type':'ldap','config':{}})
    test('sysadmin 不能创建认证提供者', isinstance(r, dict) and 'error' in r, str(r))
    r = t.get('/api/admin/agents')
    test('sysadmin 可以查看工程师列表', isinstance(r, list), str(type(r)))
    r = t.get('/api/admin/config')
    test('sysadmin 可以访问系统配置', isinstance(r, dict) and not r.get('error'), str(type(r)))

    # ---- 3. secadmin 权限边界 ----
    print('\n📋 3. Secadmin 权限边界')
    t.login('secadmin@smartcs.com', 'SecAdmin@2026')
    r = t.get('/api/admin/audit-logs')
    test('secadmin 不能查看审计日志', isinstance(r, dict) and 'error' in r, str(r))
    r = t.get('/api/admin/security-config')
    test('secadmin 可以访问安全配置', isinstance(r, dict) and not r.get('error'), str(type(r)))
    r = t.post('/api/admin/auth-providers', {'name':'test-ldap','provider_type':'ldap','config':{}})
    test('secadmin 可以创建认证提供者', isinstance(r, dict) and r.get('ok'), str(r))
    r = t.get('/api/admin/agents')
    test('secadmin 可以查看工程师列表', isinstance(r, list), str(type(r)))
    r = t.get('/api/admin/config')
    test('secadmin 不能访问系统配置', isinstance(r, dict) and r.get('error'), str(r))

    # ---- 4. audadmin 权限边界 ----
    print('\n📋 4. Audadmin 权限边界')
    t.login('audadmin@smartcs.com', 'AudAdmin@2026')
    r = t.get('/api/admin/audit-logs')
    test('audadmin 可以查看审计日志', isinstance(r, dict), str(type(r)))
    r = t.get('/api/admin/login-logs')
    test('audadmin 可以查看登录日志', isinstance(r, dict), str(type(r)))
    r = t.get('/api/admin/stats/overview')
    test('audadmin 可以查看概览统计', not r.get('error'), str(r))
    r = t.get('/api/admin/analytics')
    test('audadmin 可以查看数据分析', not r.get('error'), str(r))
    r = t.get('/api/admin/agents')
    test('audadmin 不能查看工程师列表', isinstance(r, dict) and 'error' in r, str(r))
    r = t.delete('/api/admin/agents/fake-id')
    test('audadmin 不能删除工程师', isinstance(r, dict) and ('权限' in json.dumps(r) or 'error' in r), str(r))

    # ---- 5. 删除保护 ----
    print('\n📋 5. 删除保护')
    t.login('secadmin@smartcs.com', 'SecAdmin@2026')
    # Find secadmin and audadmin IDs
    super_t = RoleTester()
    super_t.login('admin@smartcs.com', 'admin123')
    agents = super_t.get('/api/admin/agents')
    sec_ids = [a['id'] for a in agents if a['role'] == 'secadmin']
    aud_ids = [a['id'] for a in agents if a['role'] == 'audadmin']
    sys_ids = [a['id'] for a in agents if a['role'] == 'sysadmin']
    
    if sec_ids:
        # secadmin tries to delete self and last secadmin
        r = t.delete(f'/api/admin/agents/{sec_ids[0]}')
        test('不能删除自己或最后一位安全管理员', 
             isinstance(r, dict) and ('error' in r or 'permiss' in json.dumps(r)), str(r))
    if aud_ids:
        r = super_t.delete(f'/api/admin/agents/{aud_ids[0]}')
        test('不能删除最后一位审计管理员', 'error' in r, str(r))
    if sys_ids:
        r = super_t.delete(f'/api/admin/agents/{sys_ids[0]}')
        test('不能删除最后一位系统管理员', 'error' in r, str(r))

    # ---- 6. superadmin 全权限 ----
    print('\n📋 6. Superadmin 全权限')
    t.login('admin@smartcs.com', 'admin123')
    r = t.get('/api/admin/audit-logs')
    test('superadmin 可以查看审计日志', isinstance(r, dict), str(type(r)))
    r = t.get('/api/admin/security-config')
    test('superadmin 可以查看安全配置', isinstance(r, dict) and not r.get('error'), str(type(r)))
    r = t.get('/api/admin/agents')
    test('superadmin 可以查看工程师列表', isinstance(r, list), str(type(r)))
    r = t.post('/api/admin/auth-providers', {'name':'super-test','provider_type':'ldap','config':{}})
    test('superadmin 可以创建认证提供者', isinstance(r, dict) and r.get('ok'), str(r))
    r = t.post('/api/admin/config', {'api_key':'test'})
    test('superadmin 可以修改系统配置', isinstance(r, dict), str(type(r)))

    # ---- 7. 互斥约束 ----
    print('\n📋 7. 互斥约束')
    # agents.role is single-value; test that role can't be set to multiple values
    super_t = RoleTester()
    super_t.login('admin@smartcs.com', 'admin123')
    # Existing users should each have exactly one role
    agents = super_t.get('/api/admin/agents')
    for a in agents:
        ok = a['role'] in ('agent','sysadmin','secadmin','audadmin','superadmin')
        test(f'{a["email"]} 角色有效: {a["role"]}', ok, str(a['role']))
        if not ok: break

    # ---- 8. 密码策略 ----
    print('\n📋 8. 密码策略')
    sys_t = RoleTester()
    sys_t.login('sysadmin@smartcs.com', 'SysAdmin@2026')
    r = sys_t.post('/api/admin/agents', {'name':'test','email':'weak@test.com','password':'short'})
    test('弱密码被拒绝（密码策略）', isinstance(r, dict) and 'error' in r, str(r))

    # ---- 总结 ----
    print(f'\n{"="*60}')
    print(f'  结果: {PASS} 通过 / {PASS+FAIL} 总用例 ({FAIL} 失败)')
    print(f'{"="*60}')
    return FAIL == 0

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
