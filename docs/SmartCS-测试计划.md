# SmartCS 智能客服工单系统 — 全面测试计划

**版本：** v5.0  
**制定日期：** 2026-05-20  
**测试范围：** 接口集成测试 + 手动 API 验证  
**测试对象：** 部署于 `http://8.133.198.245:8080` 的生产环境

---

## 1. 测试范围

### 1.1 测试目标
- 验证全部 ✅ 已完成功能需求是否正常工作
- 验证新状态机（created→processing→resolved→rated→closed）完整生命周期
- 验证工程师级别 L1~L4 支持
- 验证知识库审核流程（提交→审核→发布）
- 验证管理后台全功能（配置/工单/用户/审计/集成）
- 验证异常/边界场景处理
- 验证安全控制（鉴权/拒绝未授权）

### 1.2 测试不覆盖
- 语音消息发送（F-USER-2b，⚠️ 需新建）
- 问题升级（F-AGENT-9，⚠️ 待开发）
- 知识沉淀审核流程完整UI（F-AGENT-10，⚠️ 部分待开发）
- 工程师在线状态与路由（F-AGENT-12，⚠️ 待开发）
- 身份切换（F-AGENT-14，⚠️ 待开发）
- 工程师绩效统计（F-AGENT-15，⚠️ 待开发）
- 移动端推送通知（F-MOBILE-5，⚠️ 待开发）
- 原生 SDK 封装（F-MOBILE-4，⚠️ 待开发）
- 安全需求 S-1~S-8（⚠️ 部分已实施，部分待开发）

---

## 2. 测试环境

| 项目 | 值 |
|------|------|
| 服务器 | 8.133.198.245（阿里云 ECS） |
| 应用访问 | http://8.133.198.245:5000 (Flask) / http://8.133.198.245:8080 (Nginx) |
| 部署路径 | `/home/deploy/smart-cs/` |
| Python | 3.8 |
| 数据库 | SQLite WAL, `/home/deploy/smart-cs/data/smartcs.db` |
| 测试脚本 | `test_smartcs_full.py` (v4.0, 78项) + `manual_api_test.py` |
| 管理员账号 | admin@smartcs.com / admin123 |
| 默认客服 | agent@smartcs.com / admin123（hash from admin:admin123） |
| L1~L4 客服 | agent_l{1-4}@smartcs.com / AIchat2026（hash from admin:AIchat2026） |

### 2.1 当前数据库状态（测试前）

| 表 | 行数 | 说明 |
|----|------|------|
| service_tickets | ~50 | processing:32, closed:16, created:1 |
| customers | 58+ | 含测试产生的临时用户 |
| agents | 8 | admin@ + agent@ + agent2@ + agent3@ + L1~L4 |
| messages | 293+ | 持续增加 |
| audit_log | 81+ | 持续增加 |
| knowledge_files | 0 | 空表 |

---

## 3. 测试用例

### 3.1 A 组 — 系统基础（6项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| A1 | F-MOBILE-1 | 首页加载正常 | 无 | 1. GET / | 返回 200，HTML 包含"智能客服"和"chat-box" |
| A2 | F-USER-4 | 登录页面加载正常 | 无 | 1. GET /login | 返回 200，包含"用户登录"或"SmartCS" |
| A3 | 3.3 状态机 | 注册页面重定向到登录 | 无 | 1. GET /register | 返回 302 或 200（指向登录页） |
| A4 | F-MOBILE-3 | PWA manifest 提供服务 | 无 | 1. GET /manifest.json | 返回 JSON，name="SmartCS 智能客服" |
| A5 | F-MOBILE-3 | Service Worker 提供服务 | 无 | 1. GET /sw.js | 返回 JS，包含"smartcs-v2" |
| A6 | F-MOBILE-3 | 静态图标可访问 | 无 | 1. GET /icon-192.svg | 返回 200 |

### 3.2 B 组 — 用户聊天流程（新状态机，8项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| B1 | F-USER-1 | 用户发送消息→创建工单 | 已注册并登录 | 1. POST /api/chat {message:"打印机无法连接"} | 返回 conversation_id，工单自动创建 |
| B2 | F-USER-1 | AI 自动回复 | B1 成功 | 1. GET /api/chat/history?conv_id={conv_id} | 历史包含 bot 角色消息 |
| B3 | F-USER-6 | 工单状态=created | B1 成功 | 1. GET /api/customer/tickets | 返回工单列表，对应工单 status="created" |
| B4 | F-AGENT-2 | created 工单对工程师隐藏 | B1 成功 | 1. Agent 登录 + GET /api/agent/tickets?status=pending | 列表中不包含此工单 |
| B5 | F-USER-3 | 转人工→status=processing | B1 成功 | 1. POST /api/customer/tickets/transfer {conv_id} | returned escalated=true |
| B6 | F-USER-1 | 聊天历史包含用户+AI 消息 | B1, B5 成功 | 1. GET /api/chat/history?conv_id={conv_id} | 包含 user 和 bot 角色，至少2条 |
| B7 | 3.3 状态机 | 转人工后工单状态=processing | B5 成功 | 1. Agent GET /api/agent/tickets?status=pending | 对应工单 status="processing" |
| B8 | — | 空消息处理 | 无 | 1. POST /api/chat {message:""} | 不崩溃，返回错误或合理响应 |

### 3.3 C 组 — 用户注册与登录（11项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| C1 | F-USER-4 | 用户注册 | 无 | POST /api/customer/register {email,password,name} | 返回 ok=true |
| C2 | F-USER-4 | 重复注册拒绝 | C1 已注册 | POST /api/customer/register {相同 email} | 返回 error 包含"已注册" |
| C3 | F-USER-4 | 用户登录 | C1 已注册 | POST /api/customer/login {email,password} | 返回 ok=true |
| C4 | F-USER-4 | 错误密码登录拒绝 | C1 已注册 | POST /api/customer/login {email,password:wrong} | 返回 error 或 ok=false |
| C5 | F-USER-4 | 未注册邮箱登录拒绝 | 无 | POST /api/customer/login {email:unregistered} | 返回 error 或 ok=false |
| C6 | F-USER-4 | 获取当前用户信息 | C3 登录后 | GET /api/customer/me | logged_in=true, email 匹配 |
| C7 | F-USER-5 | 获取用户配置信息 | C3 登录后 | GET /api/customer/profile | 返回 customer_id |
| C8 | F-USER-5 | 更新用户配置 | C3 登录后 | POST /api/customer/profile {name,phone,company} | 返回 ok=true |
| C9 | F-USER-6 | 查询用户工单历史 | C3 登录后 | GET /api/customer/tickets | 返回工单列表 |
| C10 | F-USER-4 | 用户登出 | C3 登录后 | POST /api/customer/logout | 返回 ok=true |
| C11 | F-USER-4 | 登出后状态=未登录 | C10 后 | GET /api/customer/me | logged_in=false |

### 3.4 D 组 — 客服端完整流程（新状态机，17项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| D1 | F-AGENT-1 | 工程师登录 | 无 | POST /agent/login {email,password} | 返回 ok=true, redirect 到 dashboard |
| D2 | F-AGENT-1 | 工程师登出 | D1 登录后 | POST /agent/logout | session 清除 |
| D3 | F-AGENT-2 | 待处理工单列表(仅processing) | D1 登录后 | GET /api/agent/tickets?status=pending | 返回列表（仅processing状态） |
| D4 | F-AGENT-2 | 我的工单列表 | D1 登录后 | GET /api/agent/tickets?status=mine | 返回列表 |
| D5 | F-AGENT-2 | 历史工单列表 | D1 登录后 | GET /api/agent/tickets?status=history | 返回列表（含rated/closed） |
| D6 | F-AGENT-3 | 查找待处理工单 | D3 获取列表 | 按 conversation_id 匹配 | 找到对应工单 |
| D7 | F-AGENT-3 | 受理工单(assign) | D6 找到工单 | POST /api/agent/tickets/assign {ticket_id} | ok=true |
| D8 | F-AGENT-3 | 客服加载对话 | D7 受理后 | GET /api/agent/conversation/{conv_id} | 返回 ≥2条消息 |
| D9 | F-AGENT-6 | 查看工单详情 | D7 受理后 | GET /api/agent/tickets/{tk_id} | 返回含 customer_name |
| D10 | F-AGENT-3 | 工程师发送回复 | D7 受理后 | POST /api/agent/reply {conv_id, content} | ok=true |
| D11 | F-AGENT-3 | 用户收到工程师回复 | D10 后 | GET /api/chat/history?conv_id={conv_id} | 包含 agent 角色消息 |
| D12 | F-AGENT-5 | 提请处理完成(processing→resolved) | D7 受理后 | POST /api/agent/tickets/resolve {ticket_id, notes} | ok=true |
| D13 | F-AGENT-5 | 用户收到处理完成提示 | D12 后 | GET /api/chat/history?conv_id={conv_id} | 包含 system 角色消息 |
| D14 | F-USER-6 | 用户确认+评价(resolved→rated) | D12 后 | POST /api/customer/tickets/confirm {ticket_id, rating, feedback} | ok=true |
| D15 | F-USER-6 | 用户评价服务 | D14 后（或独立） | POST /api/customer/tickets/rate {ticket_id, rating, feedback} | ok=true |
| D16 | F-AGENT-5 | 工程师关闭工单(rated→closed) | D14+D15 后 | POST /api/agent/tickets/close {ticket_id, reason, notes} | ok=true |
| D17 | F-AGENT-5 | 工单最终状态=closed | D16 后 | GET /api/agent/tickets/{tk_id} | status="closed" |

### 3.5 E 组 — 管理后台（17项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| E1 | F-ADMIN-BIZ-1 | 管理员登录 | 无 | POST /agent/login {admin@smartcs.com} | ok=true, role=admin |
| E2 | F-ADMIN-BIZ-2 | 管理后台可访问 | E1 登录后 | GET /admin/dashboard | HTML 包含"SmartCS"或"后台管理" |
| E3 | F-ADMIN-BIZ-2 | 管理员查看工单列表 | E1 登录后 | GET /api/admin/tickets?page=1&limit=10 | 返回分页工单列表 |
| E4 | F-ADMIN-BIZ-2 | 工单统计数据 | E1 登录后 | GET /api/admin/tickets/stats | 返回各状态统计 |
| E5 | F-ADMIN-BIZ-1 | 管理员查看客服列表 | E1 登录后 | GET /api/admin/agents | 返回客服列表 |
| E6 | F-ADMIN-BIZ-1 | 管理员查看用户列表 | E1 登录后 | GET /api/admin/customers?page=1 | 返回含 customers 字段 |
| E7 | F-ADMIN-BIZ-1 | 管理员查看用户详情 | E6 获 ID | GET /api/admin/customers/{cid} | 返回含 customer 字段 |
| E8 | F-ADMIN-BIZ-1 | 管理员编辑用户信息 | E7 获 CID | PUT /api/admin/customers/{cid}/profile {name,phone,company} | ok=true |
| E9 | F-ADMIN-BIZ-1 | 管理员重置用户密码 | E7 获 CID | PUT /api/admin/customers/{cid}/reset-password {password} | ok=true |
| E10 | F-ADMIN-AUDIT-1 | 审计日志查询 | E1 登录后 | GET /api/admin/audit-logs?page=1&per_page=10 | 返回含 logs 字段 |
| E11 | F-ADMIN-AUDIT-1 | 审计日志按类型筛选 | E1 登录后 | GET /api/admin/audit-logs?action=ticket.assigned | 返回筛选结果 |
| E12 | F-ADMIN-BIZ-4 | 负责系统列表 | E1 登录后 | GET /api/admin/systems | 返回系统列表 |
| E13 | F-ADMIN-BIZ-3 | 关闭原因列表 | E1 登录后 | GET /api/admin/close-reasons | 返回原因列表 |
| E14 | F-ADMIN-CONFIG-1 | 系统配置获取 | E1 登录后 | GET /api/admin/config | 返回配置 JSON |
| E15 | F-ADMIN-CONFIG-2 | IM 适配器列表 | E1 登录后 | GET /api/admin/im-adapters | 返回配置列表 |
| E16 | F-ADMIN-CONFIG-2 | 外部系统适配器列表 | E1 登录后 | GET /api/admin/external-adapters | 返回配置列表 |
| E17 | F-ADMIN-CONFIG-2 | Webhook 列表 | E1 登录后 | GET /api/admin/webhooks | 返回配置列表 |

### 3.6 E' 组 — 管理后台扩展（5项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| E18 | F-ADMIN-BIZ-7 | 数据分析接口 | E1 登录后 | GET /api/admin/analytics | 返回含 tickets_by_status |
| E19 | F-ADMIN-AUDIT-2 | 登录日志查询 | E1 登录后 | GET /api/admin/login-logs?page=1&per_page=10 | 返回含 logs |
| E20 | F-ADMIN-CONFIG-1 | 新配置字段存在 | E1 登录后 | GET /api/admin/config | 含 auto_close_min, auto_rate_hours, ticket_search_max_days, level_names |
| E21 | F-AGENT-2 | 按时间段搜索工单 | D1 登录后 | GET /api/agent/tickets?status=search&start_date=2026-01-01&end_date=2026-12-31 | 返回搜索结果 |
| E22 | F-AGENT-2 | 全部经手工单列表 | D1 登录后 | GET /api/agent/tickets?status=all_mine | 返回列表 |

### 3.7 F 组 — 知识库基础（1项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| F1 | F-ADMIN-BIZ-5 | 知识库列表可访问 | 无 | GET /api/knowledge/list | 返回列表（可能为空） |

### 3.8 G 组 — 异常场景（4项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| G1 | 10.2 安全 | 空消息处理 | 已登录 | POST /api/chat {message:""} | 不崩溃，返回错误 |
| G2 | 11.1 性能 | 超长消息处理 | 已登录 | POST /api/chat {message: 1000字符} | 不崩溃，正常处理 |
| G3 | 10.1 安全 | 未授权访问被拒绝 | 用普通用户 session | GET /api/admin/tickets | 返回 error 或拒绝 |
| G4 | 10.1 安全 | 不存在的页面返回 404 | 无 | GET /this-page-does-not-exist | 返回 HTTP 404 |

### 3.9 H 组 — 新状态机核心（15项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| H1 | 3.3 | 全链路: created→processing→resolved→rated→closed | 新建用户 | 全生命周期串行执行 | 每步状态切换正确 |
| H1a | F-USER-1 | 发消息→工单状态=created | 新注册登录 | POST chat → GET tickets | status="created" |
| H1b | F-USER-3 | 转人工→processing | H1a 后 | POST transfer → | escalated=true |
| H1c | F-AGENT-3 | 受理工单 | H1b 后 | POST assign | ok=true |
| H1d | F-AGENT-5 | 提请完成→resolved | H1c 后 | POST resolve | ok=true |
| H1e | F-USER-6 | 评价→rated | H1d 后 | POST confirm {rating} | ok=true |
| H1f | F-AGENT-5 | 关闭→closed | H1e 后 | POST close {reason} | ok=true |
| H1g | 3.3 | 最终状态=closed | H1f 后 | GET ticket detail | status="closed" |
| H4 | F-ADMIN-BIZ-2 | 管理员强制关闭任意状态工单 | 有 processing 工单 | POST /api/admin/tickets/status {ticket_id, status:closed} | ok=true |
| H7 | F-AGENT-11 | L1~L4 统一关闭权限 | 各级别工程师登录 | 各级别均可执行关闭操作 | 所有级别成功 |
| H12 | F-AGENT-2 | created 工单对工程师隐藏 | 新发消息不转人工 | 工程师列表查询 | 工单不在列表中 |
| H15 | F-AGENT-11 | level_trace 记录 | 多级工程师经手 | 最终关闭后查看工单详情 | 含 level 字段 |

### 3.10 I 组 — L1~L4 级别扩展（5项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| I1 | F-AGENT-11 | L1~L4 均可登录 | L1~L4 账号存在 | 分别用 L1~L4 登录 | 均返回 ok=true |
| I2 | F-AGENT-11 | 各等级权限相同 | 各级别登录后 | 测试关闭/转交功能 | 所有级别均可操作 |
| I3 | F-AGENT-11 | 管理后台级别配置 | 管理员登录后 | 查看客服列表可见级别 | 含 agent_level 字段 |
| I4 | 3.3 | 拦截率以最后关闭人级别为准 | 经手后由 L2 关闭 | 查 level_trace | level=最后关闭人的级别 |

### 3.11 J 组 — 知识审核流程（6项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| J1 | F-ADMIN-BIZ-5 | 工程师提交知识(含标签) | 工程师已登录 | POST /api/agent/tickets/knowledge {title,content,tags} | 返回 knowledge_id |
| J2 | F-ADMIN-BIZ-5 | 查看我的知识提交 | 工程师已登录 | GET /api/agent/knowledge/mine | 返回本人提交列表 |
| J3 | F-ADMIN-BIZ-5 | 管理员通过审核 | 有 pending 知识 | POST /api/admin/knowledge/{kid}/approve | ok=true, status→approved |
| J4 | F-ADMIN-BIZ-5 | 已通过知识可被搜索 | J3 成功后 | GET /api/knowledge/list | 列表包含已通过条目 |
| J5 | F-ADMIN-BIZ-5 | 管理员驳回知识(含原因) | 有 pending 知识 | POST /api/admin/knowledge/{kid}/reject {reason} | ok=true |
| J6 | F-ADMIN-BIZ-5 | 被驳回知识可查看原因 | J5 成功后 | GET /api/agent/knowledge/mine | 可看到驳回原因 |

### 3.12 K 组 — 知识标签与版本（4项）

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| K1 | F-ADMIN-BIZ-5a | 知识标签保存正确 | 工程师已登录 | POST knowledge with tags → GET detail | tags 字段完整保存 |
| K2 | F-ADMIN-BIZ-5b | 知识更新产生历史记录 | 有现有知识 | PUT knowledge → GET /{kid}/history | 历史记录增长 |
| K3 | F-ADMIN-BIZ-5b | 版本历史接口可访问 | 管理员已登录 | GET /api/admin/knowledge/{kid}/history | 返回列表 |
| K4 | F-ADMIN-BIZ-5b | 详情包含 created_by | 工程师已登录 | GET /api/agent/knowledge/{kid} | 含 created_by 字段 |

### 3.13 L 组 — 手动全链路测试

| ID | 需求参考 | 描述 | 前置条件 | 步骤 | 期望结果 |
|----|---------|------|---------|------|---------|
| L1 | F-USER-4~F-AGENT-5 | 完整用户生命周期 | 无 | 注册→登录→发消息→AI回复→转人工→工程师受理→工程师回复→提请完成→用户评价→工程师关闭 | 每步正确 |
| L2 | F-AGENT-4 | 工单转交 | 工单已受理 | 转交给其他工程师 | transferred_from 记录 |
| L3 | F-ADMIN-BIZ-2 | 管理员强制关闭 | 有活跃工单 | POST /api/admin/tickets/status {closed} | 工单关闭 |
| L4 | F-ADMIN-CONFIG-1 | 管理员查看系统配置 | 管理员登录后 | GET /api/admin/config | 返回完整配置 |
| L5 | 10.1 | 权限控制: 普通用户无法访问管理接口 | 用户登录后 | GET /api/admin/tickets | 返回权限错误 |
| L6 | F-USER-4 | 重复注册拒绝 | 已注册邮箱 | 再次注册 | 返回错误 |
| L7 | F-USER-4 | 错误密码登录拒绝 | 已注册 | 用错误密码登录 | 返回错误 |
| L8 | F-USER-4 | 未注册邮箱登录拒绝 | 无 | 用不存在邮箱登录 | 返回错误 |
| L9 | 10.1 | 空消息处理 | 已登录 | 发送空消息 | 不崩溃 |
| L10 | 11.1 | 超长消息处理 | 已登录 | 发送 2000 字符消息 | 不崩溃 |
| L11 | F-AGENT-11 | L1~L4 各级别登录 | 各级别账号存在 | 分别用 L1~L4 登录 | 全部成功 |

---

## 4. 测试策略

### 4.1 自动化测试
1. 运行已部署的 `test_smartcs_full.py`（v4.0 增强版，78项）
2. 输出来回比对，记录通过/失败

### 4.2 手动 API 测试
1. 通过 SSH 执行 Python 脚本
2. 覆盖完整生命周期
3. 测试边界/异常场景

### 4.3 数据库验证
1. 测试前后检查工单状态记录
2. 验证 system_config 新字段
3. 验证知识库表结构

---

## 5. 通过标准

| 等级 | 要求 |
|------|------|
| 通过 | 所有 P0 需求测试 100% 通过，失败项 ≤ 3 |
| 有条件通过 | P0 通过率 ≥ 90%，失败项 ≤ 5，无 Critical 缺陷 |
| 不通过 | P0 通过率 < 90% 或存在 Critical 功能缺陷 |
