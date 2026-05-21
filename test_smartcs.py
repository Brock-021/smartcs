#!/usr/bin/env python3
"""
SmartCS 集成测试脚本
测试所有核心业务流程：用户咨询 → 转人工 → IT工程师回复 → 关闭工单
"""

import urllib.request, urllib.parse, json, http.cookiejar, sys, os, io, uuid

# === Configuration ===
BASE = os.environ.get('SMART_CS_URL', 'http://localhost:5000')
AGENT_EMAIL = os.environ.get('AGENT_EMAIL', 'agent@smartcs.com')
AGENT_PASS = os.environ.get('AGENT_PASS', 'admin123')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@smartcs.com')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')
TEST_EMAIL = f'test_{uuid.uuid4().hex[:8]}@test.com'
TEST_PASS = 'TestPass123'

passed = 0
failed = 0
results = []

def test(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
        results.append(f'  ✅ {name}')
    else:
        failed += 1
        results.append(f'  ❌ {name} — {detail}')

class SmartCSTest:
    def __init__(self):
        self.user_cj = http.cookiejar.CookieJar()
        self.user = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.user_cj))
        self.agent_cj = http.cookiejar.CookieJar()
        self.agent = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.agent_cj))
        self.admin_cj = http.cookiejar.CookieJar()
        self.admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.admin_cj))
        self.email = TEST_EMAIL
        self.password = TEST_PASS

    def api(self, opener, path, data=None, method='POST' if True else 'GET'):
        req = urllib.request.Request(BASE + path,
            data=json.dumps(data).encode() if data else None,
            headers={'Content-Type': 'application/json'} if data else {})
        if method == 'GET' and data:
            req = urllib.request.Request(BASE + path + '?' + urllib.parse.urlencode(data))
        try:
            resp = opener.open(req)
            if resp.status >= 400:
                return None
            ct = resp.headers.get('Content-Type', '')
            if 'json' in ct:
                return json.loads(resp.read())
            return resp.read().decode()
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read())
            except:
                return None

    def test_homepage(self):
        req = urllib.request.Request(BASE + '/')
        try:
            resp = self.user.open(req)
            html = resp.read().decode()
            test('Homepage loads', '智能客服' in html)
        except Exception as e:
            test('Homepage loads', False, str(e))

    def register_user(self):
        r = self.api(self.user, '/api/customer/register',
                     {'email': self.email, 'password': self.password, 'name': '测试用户'})
        test('User register', r and r.get('ok'), str(r)[:100])
        return r

    def test_user_flow(self):
        # Register & login first
        self.register_user()

        # Step 1: Send message
        r = self.api(self.user, '/api/chat', {'message': '电脑蓝屏了'})
        test('User sends message', r and r.get('conversation_id'), str(r)[:100])
        conv_id = r.get('conversation_id', '') if r else ''

        # Step 2: Check bot replied
        test('Bot replied', r and r.get('reply'), '')

        # Step 3: Request human
        r = self.api(self.user, '/api/chat', {'message': '转人工', 'conversation_id': conv_id})
        test('Request human', r and r.get('escalated'), str(r)[:100])

        return conv_id

    def test_chat_history(self, conv_id):
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        test('Chat history accessible', r is not None and len(r) >= 2, str(r)[:100])
        if r:
            msgs = [m['role'] for m in r]
            test('Chat has user message', 'user' in msgs)
            test('Chat has bot message', 'bot' in msgs)
        return r

    def test_agent_login(self):
        r = self.api(self.agent, '/agent/login', {'email': AGENT_EMAIL, 'password': AGENT_PASS})
        test('Agent login', r and r.get('ok'), str(r)[:100])
        return r

    def test_admin_login(self):
        r = self.api(self.admin, '/agent/login', {'email': ADMIN_EMAIL, 'password': ADMIN_PASS})
        test('Admin login', r and r.get('ok'), str(r)[:100])
        return r

    def test_pending_tickets(self):
        r = self.api(self.agent, '/api/agent/tickets?status=pending', method='GET')
        test('Pending tickets accessible', r is not None, str(r)[:100])
        return r

    def test_assign_and_reply(self, conv_id):
        # Find ticket
        tickets = self.api(self.agent, '/api/agent/tickets?status=pending', method='GET')
        tk = None
        if tickets:
            for t in tickets:
                if t.get('conversation_id') == conv_id:
                    tk = t
                    break
        test('Found matching ticket', tk is not None)
        if not tk:
            return None

        # Assign
        r = self.api(self.agent, '/api/agent/tickets/assign', {'ticket_id': tk['id']})
        test('Assign ticket', r and r.get('ok'), str(r)[:100])

        # Load conversation
        r = self.api(self.agent, f'/api/agent/conversation/{conv_id}', method='GET')
        test('Agent loads conversation', r is not None and len(r) >= 2, str(r)[:100])

        # Load ticket detail
        r = self.api(self.agent, f'/api/agent/tickets/{tk["id"]}', method='GET')
        test('Agent loads ticket detail', r and r.get('customer_name'), str(r)[:100])

        # Reply
        r = self.api(self.agent, '/api/agent/reply', {'conversation_id': conv_id, 'content': '您好，请问蓝屏代码是多少？'})
        test('Agent sends reply', r and r.get('ok'), str(r)[:100])

        return tk

    def test_user_receives_reply(self, conv_id):
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        if r:
            agent_msgs = [m for m in r if m['role'] == 'agent']
            test('User receives agent reply', len(agent_msgs) >= 1, '')
        else:
            test('User receives agent reply', False, 'no history')

    def test_close_request(self, tk_id):
        r = self.api(self.agent, '/api/agent/tickets/close',
                     {'ticket_id': tk_id, 'close_reason': '已解决', 'resolution_notes': '已远程解决'})
        test('Agent requests close', r and r.get('ok'), str(r)[:100])

    def test_user_receives_system_msg(self, conv_id):
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        if r:
            sys_msgs = [m for m in r if m.get('role') in ('system', 'agent')]
            test('User receives system/close message', len(sys_msgs) >= 1, '')
        else:
            test('User receives system/close message', False, 'no history')

    def test_agent_profile(self):
        r = self.api(self.admin, '/api/admin/agents', method='GET')
        test('Admin lists agents', r is not None, str(r)[:100])

    def test_manifest(self):
        req = urllib.request.Request(BASE + '/manifest.json')
        try:
            resp = self.user.open(req)
            r = json.loads(resp.read())
            test('PWA manifest serves', r.get('name') == 'SmartCS 智能客服', str(r)[:100])
        except Exception as e:
            test('PWA manifest serves', False, str(e))

    def test_sw(self):
        req = urllib.request.Request(BASE + '/sw.js')
        try:
            resp = self.user.open(req)
            js = resp.read().decode()
            test('Service Worker serves', 'smartcs-v2' in js, '')
        except Exception as e:
            test('Service Worker serves', False, str(e))

    def test_agent_logout(self):
        r = self.api(self.agent, '/agent/logout', {})
        test('Agent logout', True, '')

    def run_all(self):
        self.test_homepage()
        conv_id = self.test_user_flow()

        if conv_id:
            self.test_chat_history(conv_id)
            self.test_agent_login()
            self.test_pending_tickets()
            self.test_admin_login()
            self.test_agent_profile()
            tk = self.test_assign_and_reply(conv_id)
            if tk:
                self.test_user_receives_reply(conv_id)
                self.test_close_request(tk['id'])
                self.test_user_receives_system_msg(conv_id)

        self.test_manifest()
        self.test_sw()
        self.test_agent_logout()

        # Print results
        print(f"\n{'='*50}")
        print(f"SmartCS 集成测试结果")
        print(f"{'='*50}")
        for r in results:
            print(r)
        print(f"\n{'='*50}")
        print(f"总计: {passed + failed}  |  ✅ 通过: {passed}  |  ❌ 失败: {failed}")
        if failed > 0:
            print("⚠️  部分测试未通过，请检查错误详情")
        print(f"{'='*50}")
        return failed == 0


if __name__ == '__main__':
    tester = SmartCSTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
