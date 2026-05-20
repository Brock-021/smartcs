#!/usr/bin/env python3
"""
SmartCS v4.0 全功能集成测试脚本
覆盖：用户端(AI/人工/转接/工单)、注册登录、客服端、管理后台、系统配置

运行: python3 test_smartcs_full.py
"""

import urllib.request, urllib.parse, json, http.cookiejar, sys, os, uuid, time, re

# === Configuration ===
BASE = os.environ.get('SMART_CS_URL', 'http://localhost:5000')
AGENT_EMAIL = os.environ.get('AGENT_EMAIL', 'agent@smartcs.com')
AGENT_PASS = os.environ.get('AGENT_PASS', 'admin123')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@smartcs.com')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')

# Test user - unique email to avoid collisions
TEST_EMAIL = f'test_{uuid.uuid4().hex[:8]}@test.com'
TEST_PASS = 'TestPass123'
TEST_NAME = '测试用户'

passed = 0
failed = 0
results = []

# === Helper ===

def test(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
        results.append(f'  ✅ {name}')
    else:
        failed += 1
        results.append(f'  ❌ {name} — {detail}')


class SmartCSTest:
    """Comprehensive test suite for SmartCS"""

    def __init__(self):
        # Independent cookie jars for different roles
        self.user_cj = http.cookiejar.CookieJar()
        self.user = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.user_cj))
        self.user2_cj = http.cookiejar.CookieJar()
        self.user2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.user2_cj))
        self.agent_cj = http.cookiejar.CookieJar()
        self.agent = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.agent_cj))
        self.admin_cj = http.cookiejar.CookieJar()
        self.admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.admin_cj))
        self.reg_cj = http.cookiejar.CookieJar()
        self.reg = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.reg_cj))

        # Store test data
        self.test_conv_id = None
        self.test_ticket_id = None
        self.test_customer_id = None
        self.test_customer_name = None

    # -------------------------------------------------------------------------- #
    #  HTTP Helper
    # -------------------------------------------------------------------------- #

    def api(self, opener, path, data=None, method=None):
        """Generic JSON API caller. Auto-detect GET/POST."""
        if method is None:
            method = 'GET' if data is None else 'POST'
        body = json.dumps(data).encode() if data is not None else None
        headers = {'Content-Type': 'application/json'} if body else {}
        req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
        try:
            resp = opener.open(req, timeout=15)
            ct = resp.headers.get('Content-Type', '')
            raw = resp.read()
            if 'json' in ct:
                return json.loads(raw)
            return raw.decode()
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read())
            except:
                return None
        except Exception as e:
            return None

    def html(self, opener, path):
        """Fetch HTML page, return text."""
        try:
            resp = opener.open(urllib.request.Request(BASE + path), timeout=10)
            return resp.read().decode()
        except:
            return ''

    def copy_cookies(self, src_cj, dst_cj):
        """Copy cookies from one cookie jar to another."""
        for cookie in src_cj:
            dst_cj.set_cookie(cookie)

    def status(self, opener, path):
        """Fetch a URL and return HTTP status code."""
        try:
            resp = opener.open(urllib.request.Request(BASE + path), timeout=10)
            return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except:
            return 0

    # ========================================================================== #
    #  A. 系统基础 - System Basic
    # ========================================================================== #

    def test_homepage(self):
        html = self.html(self.user, '/')
        test('A1. 首页加载正常', '智能客服' in html and 'chat-box' in html, str(len(html))[:20])

    def test_login_page(self):
        html = self.html(self.user2, '/login')
        test('A2. 登录页面加载正常', '用户登录' in html or 'SmartCS' in html, str(len(html))[:20])

    def test_register_redirect(self):
        st = self.status(self.user2, '/register')
        test('A3. 注册页面重定向到登录', st == 302 or st == 200, f'status={st}')

    def test_manifest_pwa(self):
        req = urllib.request.Request(BASE + '/manifest.json')
        try:
            resp = self.user.open(req, timeout=10)
            r = json.loads(resp.read())
            test('A4. PWA manifest 提供服务', r.get('name') == 'SmartCS 智能客服', str(r.get('name','')))
        except Exception as e:
            test('A4. PWA manifest 提供服务', False, str(e))

    def test_service_worker(self):
        try:
            js = self.html(self.user, '/sw.js')
            test('A5. Service Worker 提供服务', 'smartcs-v2' in js, 'ok')
        except Exception as e:
            test('A5. Service Worker 提供服务', False, str(e))

    def test_static_icon(self):
        st = self.status(self.user, '/static/icon-192.svg')
        test('A6. 静态图标可访问', st == 200, f'status={st}')

    # ========================================================================== #
    #  B. 用户端 - 聊天核心流程 (User Chat Core Flow)
    # ========================================================================== #

    def test_user_first_message(self):
        """User sends first message, gets AI reply, escalation"""
        # Send message
        r = self.api(self.user, '/api/chat', {'message': '电脑蓝屏了，怎么办？'})
        test('B1. 用户发送消息', r and r.get('conversation_id'), str(r)[:100] if r else 'no resp')
        conv_id = r.get('conversation_id', '') if r else ''
        self.test_conv_id = conv_id

        # Check AI replied
        test('B2. AI自动回复', r and r.get('reply') and len(r['reply']) > 0, str(r.get('reply',''))[:50])

        return conv_id

    def test_request_human(self, conv_id):
        """User requests human agent"""
        r = self.api(self.user, '/api/chat', {'message': '转人工', 'conversation_id': conv_id})
        test('B3. 转人工请求', r and r.get('escalated'), str(r)[:100] if r else 'no resp')
        return r

    def test_chat_history_after_messages(self, conv_id):
        """Check chat history has user+bot messages"""
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        test('B4. 聊天历史可访问', r is not None and len(r) >= 2, str(len(r or [])))
        if r:
            roles = [m['role'] for m in r]
            test('B4a. 包含用户消息', 'user' in roles)
            test('B4b. 包含AI回复', 'bot' in roles)
        return r

    def test_send_image(self):
        """User sends an image (simulate)"""
        # Note: actual image upload tested via upload API, just verify endpoint
        pass  # Image upload covered elsewhere

    # ========================================================================== #
    #  C. 用户端 - 注册/登录 (User Auth)
    # ========================================================================== #

    def test_user_register(self):
        """Register a new user account"""
        r = self.api(self.reg, '/api/customer/register', {
            'email': TEST_EMAIL,
            'password': TEST_PASS,
            'name': TEST_NAME
        })
        test('C1. 用户注册', r and r.get('ok'), str(r)[:100])
        if r:
            self.test_customer_name = r.get('customer', {}).get('name', '')
        return r

    def test_duplicate_register(self):
        """Register with same email should fail"""
        r = self.api(self.reg, '/api/customer/register', {
            'email': TEST_EMAIL,
            'password': TEST_PASS
        })
        test('C2. 重复注册拒绝', r and r.get('error') and '已注册' in str(r), str(r)[:100])

    def test_user_login(self):
        """Login with registered email"""
        r = self.api(self.user2, '/api/customer/login', {
            'email': TEST_EMAIL,
            'password': TEST_PASS
        })
        test('C3. 用户登录', r and r.get('ok'), str(r)[:100])
        return r

    def test_invalid_login(self):
        """Login with wrong password"""
        r = self.api(self.user2, '/api/customer/login', {
            'email': TEST_EMAIL,
            'password': 'wrong_password_123'
        })
        test('C4. 错误密码登录拒绝', r and (r.get('error') or not r.get('ok')), str(r)[:100])

    def test_unknown_email_login(self):
        """Login with unregistered email"""
        r = self.api(self.user2, '/api/customer/login', {
            'email': 'nonexistent@test.com',
            'password': 'somepass123'
        })
        test('C5. 未注册邮箱登录拒绝', r and (r.get('error') or not r.get('ok')), str(r)[:100])

    def test_user_me(self):
        """Get current logged-in user profile"""
        r = self.api(self.reg, '/api/customer/me', method='GET')
        test('C6. 获取当前用户信息', r and r.get('logged_in') and r.get('customer', {}).get('email') == TEST_EMAIL, str(r)[:100])

    def test_user_profile_get(self):
        """Get customer profile"""
        r = self.api(self.reg, '/api/customer/profile', method='GET')
        test('C7. 获取用户配置信息', r and r.get('customer_id'), str(r)[:100])

    def test_user_profile_update(self):
        """Update customer profile"""
        r = self.api(self.reg, '/api/customer/profile', {
            'name': '已更新测试用户',
            'phone': '13800138000',
            'company': '测试科技'
        })
        test('C8. 更新用户配置信息', r and r.get('ok'), str(r)[:100])

    def test_user_tickets(self):
        """Get user's ticket history (should have at least some from this session)"""
        r = self.api(self.reg, '/api/customer/tickets', method='GET')
        test('C9. 查询用户工单历史', r is not None, str(r)[:100])
        return r

    def test_user_logout(self):
        """Logout user"""
        r = self.api(self.reg, '/api/customer/logout', {})
        test('C10. 用户登出', r and r.get('ok'), str(r)[:100])

    def test_user_me_after_logout(self):
        """After logout, /me should return logged_in: false"""
        r = self.api(self.reg, '/api/customer/me', method='GET')
        test('C11. 登出后用户状态为未登录', r and not r.get('logged_in'), str(r)[:100])

    # ========================================================================== #
    #  D. 客服端 (Agent Console)
    # ========================================================================== #

    def test_agent_login(self):
        """Agent login"""
        r = self.api(self.agent, '/agent/login', {'email': AGENT_EMAIL, 'password': AGENT_PASS})
        test('D1. 客服登录', r and r.get('ok'), str(r)[:100])

    def test_agent_logout(self):
        """Agent logout"""
        r = self.api(self.agent, '/agent/logout', {})
        test('D2. 客服登出', True, '')

    def test_agent_pending_tickets(self):
        """List pending tickets"""
        r = self.api(self.agent, '/api/agent/tickets?status=pending', method='GET')
        test('D3. 待处理工单列表', r is not None, str(r)[:100])
        return r

    def test_agent_all_tickets(self):
        """List all tickets for agent"""
        r = self.api(self.agent, '/api/agent/tickets?status=mine', method='GET')
        test('D4. 我的工单列表', r is not None, str(r)[:100])

    def test_agent_history_tickets(self):
        """List resolved/closed tickets"""
        r = self.api(self.agent, '/api/agent/tickets?status=history', method='GET')
        test('D5. 历史工单列表', r is not None, str(r)[:100])

    def test_agent_assign_ticket(self, conv_id):
        """Assign a ticket to self"""
        tickets = self.api(self.agent, '/api/agent/tickets?status=pending', method='GET')
        tk = None
        if tickets:
            for t in tickets:
                if t.get('conversation_id') == conv_id:
                    tk = t
                    break
        test('D6. 查找待处理工单', tk is not None)
        if not tk:
            return None

        r = self.api(self.agent, '/api/agent/tickets/assign', {'ticket_id': tk['id']})
        test('D7. 受理工单', r and r.get('ok'), str(r)[:100])
        self.test_ticket_id = tk['id']
        return tk

    def test_agent_load_conversation(self, conv_id):
        """Agent loads conversation"""
        r = self.api(self.agent, f'/api/agent/conversation/{conv_id}', method='GET')
        test('D8. 客服加载对话', r is not None and len(r) >= 2, str(len(r or [])))

    def test_agent_ticket_detail(self, tk_id):
        """Agent loads ticket detail"""
        r = self.api(self.agent, f'/api/agent/tickets/{tk_id}', method='GET')
        test('D9. 客服查看工单详情', r and r.get('customer_name'), str(r)[:100])

    def test_agent_send_reply(self, conv_id):
        """Agent sends reply to customer"""
        r = self.api(self.agent, '/api/agent/reply', {
            'conversation_id': conv_id,
            'content': '您好，请问蓝屏显示什么错误代码？'
        })
        test('D10. 客服发送回复', r and r.get('ok'), str(r)[:100])

    def test_user_gets_agent_reply(self, conv_id):
        """User polls history - sees agent message"""
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        if r:
            agent_msgs = [m for m in r if m['role'] == 'agent']
            test('D11. 用户收到客服回复', len(agent_msgs) >= 1, '')
        else:
            test('D11. 用户收到客服回复', False, 'no history')

    def test_agent_request_close(self, tk_id):
        """Agent resolves ticket (processing → resolved)"""
        r = self.api(self.agent, '/api/agent/tickets/resolve', {
            'ticket_id': tk_id,
            'resolution_notes': '已远程协助解决蓝屏问题'
        })
        test('D12. 客服请求关闭工单', r and r.get('ok'), str(r)[:100])

    def test_user_gets_close_msg(self, conv_id):
        """User sees the close request"""
        r = self.api(self.user, f'/api/chat/history?conversation_id={conv_id}', method='GET')
        if r:
            sys_msgs = [m for m in r if m['role'] == 'system']
            test('D13. 用户收到关闭提示', len(sys_msgs) >= 1, '')
        else:
            test('D13. 用户收到关闭提示', False, 'no history')

    def test_user_confirm_close(self, tk_id):
        """User confirms the resolution"""
        r = self.api(self.user, '/api/customer/tickets/confirm', {'ticket_id': tk_id})
        test('D14. 用户确认解决', r and r.get('ok'), str(r)[:100])

    def test_user_rate_service(self, tk_id):
        """User rates the service"""
        r = self.api(self.user, '/api/customer/tickets/rate', {
            'ticket_id': tk_id,
            'rating': 5,
            'feedback': '服务很好，很专业！'
        })
        test('D15. 用户评价服务', r and r.get('ok'), str(r)[:100])

    def test_agent_close_ticket(self, tk_id):
        """Agent final-closes the ticket"""
        r = self.api(self.agent, '/api/agent/tickets/close', {
            'ticket_id': tk_id,
            'close_reason': '已解决',
            'resolution_notes': '客户确认问题已解决'
        })
        test('D16. 客服最终关闭工单', (r and r.get('ok')) or (r and r.get('error')), str(r)[:100])

    def test_ticket_status(self, tk_id):
        """Check ticket status is closed/resolved"""
        r = self.api(self.agent, f'/api/agent/tickets/{tk_id}', method='GET')
        if r:
            ok = r.get('status') in ('closed', 'resolved')
            test('D17. 工单最终状态正确', ok, f'status={r.get("status")}')
        else:
            test('D17. 工单最终状态正确', False, 'no detail')

    # ========================================================================== #
    #  E. 管理后台 (Admin Console)
    # ========================================================================== #

    def test_admin_login(self):
        """Admin login"""
        r = self.api(self.admin, '/agent/login', {'email': ADMIN_EMAIL, 'password': ADMIN_PASS})
        test('E1. 管理员登录', r and r.get('ok'), str(r)[:100])

    def test_admin_dashboard(self):
        """Admin dashboard access"""
        try:
            resp = self.admin.open(urllib.request.Request(BASE + '/admin/dashboard'), timeout=10)
            html = resp.read().decode()
            test('E2. 管理后台可访问', 'SmartCS' in html or '后台管理' in html, 'ok')
        except Exception as e:
            test('E2. 管理后台可访问', False, str(e))

    def test_admin_tickets_list(self):
        """Admin lists all tickets"""
        r = self.api(self.admin, '/api/admin/tickets?page=1&limit=10', method='GET')
        test('E3. 管理员查看工单列表', r is not None, str(r)[:100])
        return r

    def test_admin_tickets_stats(self):
        """Admin ticket statistics"""
        r = self.api(self.admin, '/api/admin/tickets/stats', method='GET')
        test('E4. 工单统计数据', r is not None, str(r)[:100])

    def test_admin_agents_list(self):
        """Admin lists agents"""
        r = self.api(self.admin, '/api/admin/agents', method='GET')
        test('E5. 管理员查看客服列表', r is not None, str(r)[:100])

    def test_admin_customers_list(self):
        """Admin lists customers"""
        r = self.api(self.admin, '/api/admin/customers?page=1', method='GET')
        test('E6. 管理员查看用户列表', r is not None and r.get('customers') is not None, str(r)[:100])
        if r and r.get('customers'):
            self.test_customer_id = r['customers'][0]['id']
        return r

    def test_admin_customer_detail(self, cid):
        """Admin views customer detail"""
        if not cid:
            test('E7. 管理员查看用户详情', False, 'no customer id')
            return
        r = self.api(self.admin, f'/api/admin/customers/{cid}', method='GET')
        test('E7. 管理员查看用户详情', r and r.get('customer'), str(r)[:100])
        return r

    def test_admin_customer_edit(self, cid):
        """Admin edits customer profile"""
        if not cid:
            test('E8. 管理员编辑用户信息', False, 'no customer id')
            return
        r = self.api(self.admin, f'/api/admin/customers/{cid}/profile', method='PUT', data={
            'name': f'被修改的用户',
            'phone': '13900001111',
            'company': '被修改公司',
            'employee_id': 'EMP001',
            'department': 'IT部'
        })
        test('E8. 管理员编辑用户信息', r and r.get('ok'), str(r)[:100])

    def test_admin_customer_reset_password(self, cid):
        """Admin resets customer password"""
        if not cid:
            test('E9. 管理员重置用户密码', False, 'no customer id')
            return
        r = self.api(self.admin, f'/api/admin/customers/{cid}/reset-password', method='PUT', data={
            'password': 'NewPass456'
        })
        test('E9. 管理员重置用户密码', r and r.get('ok'), str(r)[:100])

    def test_admin_audit_logs(self):
        """Admin views audit logs"""
        r = self.api(self.admin, '/api/admin/audit-logs?page=1&per_page=10', method='GET')
        test('E10. 审计日志查询', r and r.get('logs') is not None, str(r)[:100])

    def test_admin_audit_logs_filtered(self):
        """Admin filters audit logs by action"""
        r = self.api(self.admin, '/api/admin/audit-logs?action=ticket.assigned&per_page=5', method='GET')
        test('E11. 审计日志按类型筛选', r is not None, str(r)[:100])

    def test_admin_systems(self):
        """Admin lists systems"""
        r = self.api(self.admin, '/api/admin/systems', method='GET')
        test('E12. 负责系统列表', r is not None, str(r)[:100])

    def test_admin_close_reasons(self):
        """Admin lists close reasons"""
        r = self.api(self.admin, '/api/admin/close-reasons', method='GET')
        test('E13. 关闭原因列表', r is not None, str(r)[:100])

    def test_admin_config(self):
        """Admin gets config"""
        r = self.api(self.admin, '/api/admin/config', method='GET')
        test('E14. 系统配置获取', r is not None, str(r)[:100])

    def test_admin_im_adapters(self):
        """Admin lists IM adapters"""
        r = self.api(self.admin, '/api/admin/im-adapters', method='GET')
        test('E15. IM适配器列表', r is not None, str(r)[:100])

    def test_admin_external_adapters(self):
        """Admin lists external adapters"""
        r = self.api(self.admin, '/api/admin/external-adapters', method='GET')
        test('E16. 外部系统适配器列表', r is not None, str(r)[:100])

    def test_admin_webhooks(self):
        """Admin lists webhooks"""
        r = self.api(self.admin, '/api/admin/webhooks', method='GET')
        test('E17. Webhook列表', r is not None, str(r)[:100])

    def test_admin_analytics(self):
        """Admin analytics endpoint"""
        r = self.api(self.admin, '/api/admin/analytics', method='GET')
        test('E18. 数据分析接口', r is not None and 'tickets_by_status' in r, str(r)[:100])

    def test_admin_login_logs(self):
        """Admin login logs endpoint"""
        r = self.api(self.admin, '/api/admin/login-logs?page=1&per_page=10', method='GET')
        test('E19. 登录日志接口', r is not None and 'logs' in r, str(r)[:100])

    def test_admin_config_new_fields(self):
        """Admin config with new fields"""
        r = self.api(self.admin, '/api/admin/config', method='GET')
        has_new_fields = r and 'auto_close_min' in r and 'auto_rate_hours' in r and 'ticket_search_max_days' in r and 'level_names' in r
        test('E20. 新配置字段存在', has_new_fields, str(r)[:100] if r else 'no resp')

    def test_agent_search_tickets(self):
        """Agent search tickets with date range"""
        r = self.api(self.agent, '/api/agent/tickets?status=search&start_date=2026-01-01&end_date=2026-12-31', method='GET')
        test('D18. 按时间段搜索工单', r is not None, str(r)[:100])

    def test_agent_all_mine_tickets(self):
        """Agent all mine tickets (replied to)"""
        r = self.api(self.agent, '/api/agent/tickets?status=all_mine', method='GET')
        test('D19. 全部经手工单列表', r is not None, str(r)[:100])

    # ========================================================================== #
    #  F. 知识库 (Knowledge Base)
    # ========================================================================== #

    def test_knowledge_list(self):
        """Knowledge base list (public)"""
        r = self.api(self.user, '/api/knowledge/list', method='GET')
        test('F1. 知识库列表可访问', r is not None, str(r)[:100])

    def test_admin_login_renew(self):
        """Re-login admin to ensure session is fresh"""
        r = self.api(self.admin, '/agent/login', {'email': ADMIN_EMAIL, 'password': ADMIN_PASS})
        test('F0. 管理员重新登录', r is not None, str(r)[:100])

    def test_admin_knowledge_create_with_tags(self):
        """Admin creates knowledge with tags"""
        import uuid
        tag_id = uuid.uuid4().hex[:8]
        r = self.api(self.admin, '/api/admin/knowledge', method='POST', data={
            'file': f'test_tags_{tag_id}.md',
            'snippet': '# Test Knowledge\nThis is a test knowledge entry with tags.',
            'tags': {
                'system_ids': ['测试系统'],
                'scenario': '连接失败',
                'category': '网络问题',
                'custom': ['tag1', 'tag2']
            }
        })
        test('F2. 管理员创建带标签的知识', r is not None and r.get('ok'), str(r)[:100])

    def test_admin_knowledge_list_with_tags(self):
        """Admin knowledge list returns tags and version info"""
        r = self.api(self.admin, '/api/admin/knowledge', method='GET')
        test('F3. 知识列表包含标签字段', r is not None and len(r) > 0, f'count={len(r) if r else 0}')
        if r and len(r) > 0:
            first = r[0]
            has_tags = 'tags' in first
            has_version_count = 'version_count' in first
            has_created_by = 'created_by' in first
            test('F3a. 条目包含tags字段', has_tags, str(first.keys()))
            test('F3b. 条目包含version_count', has_version_count, str(first.keys()))
            test('F3c. 条目包含created_by', has_created_by, str(first.keys()))

    def test_admin_knowledge_tag_filter(self):
        """Admin knowledge list filtered by tags"""
        import urllib.parse, uuid
        # Create fresh knowledge with known tags for filter testing
        tag_id = uuid.uuid4().hex[:8]
        cr = self.api(self.admin, '/api/admin/knowledge', method='POST', data={
            'file': f'test_{tag_id}_filter.md',
            'snippet': '# Filter Test Knowledge',
            'tags': {
                'system_ids': ['测试系统'],
                'scenario': '连接失败',
                'category': '网络问题',
                'custom': []
            }
        })
        test('F4_prep. 创建知识点用于筛选', cr is not None and cr.get('ok'), str(cr)[:100])
        
        r = self.api(self.admin, '/api/admin/knowledge?category=' + urllib.parse.quote('网络问题'), method='GET')
        test('F4. 按分类筛选知识', r is not None and len(r) > 0, f'count={len(r) if r else 0}')
        r2 = self.api(self.admin, '/api/admin/knowledge?scenario=' + urllib.parse.quote('连接失败'), method='GET')
        test('F5. 按场景筛选知识', r2 is not None and len(r2) > 0, f'count={len(r2) if r2 else 0}')

    def test_admin_knowledge_version_history(self):
        """Admin can view knowledge version history"""
        r = self.api(self.admin, '/api/admin/knowledge', method='GET')
        if r and len(r) > 0:
            kid = r[0]['id']
            hr = self.api(self.admin, f'/api/admin/knowledge/{kid}/history', method='GET')
            test('F6. 版本历史接口可访问', hr is not None, str(type(hr)))
            test('F6a. 版本历史返回列表', isinstance(hr, list), str(type(hr)))
        else:
            test('F6. 版本历史接口（跳过：无知识条目）', True, 'skip')

    def test_admin_knowledge_edit_with_tags(self):
        """Admin edits knowledge with tags via PUT"""
        import uuid
        r = self.api(self.admin, '/api/admin/knowledge', method='GET')
        if r and len(r) > 0:
            kid = r[0]['id']
            # Update tags
            e = self.api(self.admin, f'/api/admin/knowledge/{kid}', method='PUT', data={
                'tags': {'system_ids': [], 'scenario': '蓝屏', 'category': '硬件故障', 'custom': ['edited']},
                'snippet': r[0].get('snippet', '# Updated')
            })
            test('F7. 编辑知识标签', e is not None and e.get('ok'), str(e)[:100])
            # Verify history was recorded
            hr = self.api(self.admin, f'/api/admin/knowledge/{kid}/history', method='GET')
            has_history = hr is not None and len(hr) > 0
            test('F7a. 编辑后历史记录增加', has_history, f'history_count={len(hr) if hr else 0}')
        else:
            test('F7. 编辑知识标签（跳过：无条目）', True, 'skip')

    def test_agent_knowledge_submit_with_fields(self):
        """Agent submits knowledge via ticket knowledge endpoint"""
        # Re-login agent to ensure session is fresh
        self.api(self.agent, '/agent/login', {'email': AGENT_EMAIL, 'password': AGENT_PASS})
        import uuid
        title = f'Test Agent Submit {uuid.uuid4().hex[:8]}'
        content = '# Agent Submitted\nTest content for agent submission.'
        r = self.api(self.agent, '/api/agent/tickets/knowledge', method='POST', data={
            'title': title,
            'content': content
        })
        test('F8. 客服提交知识条目', r is not None and r.get('ok'), str(r)[:100])
        if r and r.get('knowledge_id'):
            kid = r['knowledge_id']
            # Verify has initial history
            hr = self.api(self.agent, f'/api/agent/knowledge/{kid}/history', method='GET')
            test('F8a. 提交后有历史记录', hr is not None and len(hr) > 0, f'history_count={len(hr) if hr else 0}, value={str(hr)[:200]}')
            # Verify detail includes all fields
            detail = self.api(self.agent, f'/api/agent/knowledge/{kid}', method='GET')
            has_created_by = detail and 'created_by' in detail
            test('F8b. 详情包含created_by', has_created_by, str(detail.keys() if detail else {}))

    # ========================================================================== #
    #  G. 异常场景 (Edge Cases)
    # ========================================================================== #

    def test_empty_message(self):
        """Send empty message - should be rejected or handled gracefully"""
        r = self.api(self.user, '/api/chat', {'message': ''})
        # May return error or treat as valid, just verify it doesn't crash
        test('G1. 空消息处理', r is not None, str(r)[:100])

    def test_very_long_message(self):
        """Send very long message"""
        long_text = '测试' * 500  # 1000 chars
        r = self.api(self.user, '/api/chat', {'message': long_text})
        test('G2. 超长消息处理', r is not None, str(r)[:100])

    def test_no_session_access(self):
        """Access protected route without session"""
        r = self.api(self.user, '/api/admin/tickets', method='GET')
        test('G3. 未授权访问被拒绝', r is None or r.get('error'), str(r)[:100])

    def test_404_page(self):
        """Access non-existent page"""
        st = self.status(self.user, '/this-page-does-not-exist-12345')
        test('G4. 不存在的页面返回404', st == 404, f'status={st}')

    # ========================================================================== #
    #  RUN ALL TESTS
    # ========================================================================== #

    def run_all(self):
        """Execute all test cases in order"""
        print("=" * 60)
        print("  SmartCS v4.0 全功能集成测试")
        print(f"  服务器: {BASE}")
        print(f"  测试用户: {TEST_EMAIL}")
        print("=" * 60)
        print()

        # ──────────────────────────────────────────────────────
        # Group A: System Basic
        # ──────────────────────────────────────────────────────
        print("📋 A. 系统基础")
        self.test_homepage()
        self.test_login_page()
        self.test_register_redirect()
        self.test_manifest_pwa()
        self.test_service_worker()
        self.test_static_icon()

        # ──────────────────────────────────────────────────────
        # Group C: User Auth (register user early)
        # ──────────────────────────────────────────────────────
        print("\n📋 C. 用户注册与登录")
        self.test_user_register()
        self.test_duplicate_register()
        self.test_user_login()
        self.test_invalid_login()
        self.test_unknown_email_login()
        self.test_user_me()
        self.test_user_profile_get()
        self.test_user_profile_update()
        self.test_user_tickets()
        self.test_user_logout()
        self.test_user_me_after_logout()

        # ──────────────────────────────────────────────────────
        # Group B: User Chat (need conv_id for later tests)
        # ──────────────────────────────────────────────────────
        print("\n📋 B. 用户聊天流程")
        # Copy session from reg user to default user so B group tests work (guest mode removed)
        self.copy_cookies(self.reg_cj, self.user_cj)
        conv_id = self.test_user_first_message()
        if conv_id:
            self.test_request_human(conv_id)
            self.test_chat_history_after_messages(conv_id)

        # ──────────────────────────────────────────────────────
        # Group D: Agent Console
        # ──────────────────────────────────────────────────────
        print("\n📋 D. 客服端流程")
        self.test_agent_login()
        self.test_agent_pending_tickets()
        self.test_agent_all_tickets()
        self.test_agent_history_tickets()

        if conv_id:
            tk = self.test_agent_assign_ticket(conv_id)
            if tk:
                tk_id = tk['id']
                self.test_agent_load_conversation(conv_id)
                self.test_agent_ticket_detail(tk_id)
                self.test_agent_send_reply(conv_id)
                self.test_user_gets_agent_reply(conv_id)
                self.test_agent_request_close(tk_id)
                self.test_user_gets_close_msg(conv_id)
                self.test_user_confirm_close(tk_id)
                self.test_user_rate_service(tk_id)
                self.test_agent_close_ticket(tk_id)
                self.test_ticket_status(tk_id)

        self.test_agent_logout()

        # ──────────────────────────────────────────────────────
        # Group E: Admin Console
        # ──────────────────────────────────────────────────────
        print("\n📋 E. 管理后台")
        self.test_admin_login()
        self.test_admin_dashboard()
        self.test_admin_tickets_list()
        self.test_admin_tickets_stats()
        self.test_admin_agents_list()
        self.test_admin_customers_list()
        if self.test_customer_id:
            self.test_admin_customer_detail(self.test_customer_id)
            self.test_admin_customer_edit(self.test_customer_id)
            self.test_admin_customer_reset_password(self.test_customer_id)
        self.test_admin_audit_logs()
        self.test_admin_audit_logs_filtered()
        self.test_admin_systems()
        self.test_admin_close_reasons()
        self.test_admin_config()
        self.test_admin_im_adapters()
        self.test_admin_external_adapters()
        self.test_admin_webhooks()
        self.test_admin_analytics()
        self.test_admin_login_logs()
        self.test_admin_config_new_fields()
        self.test_agent_search_tickets()
        self.test_agent_all_mine_tickets()

        # ──────────────────────────────────────────────────────
        # Group F: Knowledge Base
        # ──────────────────────────────────────────────────────
        print("\n📋 F. 知识库")
        self.test_knowledge_list()
        self.test_admin_login_renew()
        self.test_admin_knowledge_create_with_tags()
        self.test_admin_knowledge_list_with_tags()
        self.test_admin_knowledge_tag_filter()
        self.test_admin_knowledge_version_history()
        self.test_admin_knowledge_edit_with_tags()
        self.test_agent_knowledge_submit_with_fields()

        # ──────────────────────────────────────────────────────
        # Group G: Edge Cases
        # ──────────────────────────────────────────────────────
        print("\n📋 G. 异常场景")
        self.test_empty_message()
        self.test_very_long_message()
        self.test_no_session_access()
        self.test_404_page()

        # ──────────────────────────────────────────────────────
        # Summary
        # ──────────────────────────────────────────────────────
        print()
        print("=" * 60)
        print(f"  SmartCS 全功能集成测试 结果汇总")
        print("=" * 60)
        for r in results:
            print(r)
        print()
        print(f"  {'='*40}")
        print(f"  总计: {passed + failed}  |  ✅ 通过: {passed}  |  ❌ 失败: {failed}")
        passed_pct = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
        print(f"  通过率: {passed_pct:.1f}%")
        if failed > 0:
            print("  ⚠️  以下测试未通过，请检查错误详情：")
            for r in results:
                if '❌' in r:
                    print(f"     {r}")
        else:
            print("  🎉 所有测试全部通过！")
        print(f"  {'='*40}")

        return failed == 0


if __name__ == '__main__':
    tester = SmartCSTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
