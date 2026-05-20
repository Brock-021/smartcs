# SmartCS 智能客服工单系统 — 测试计划

**关联文档：** `docs/SmartCS-需求文档.md` v5.6、`docs/SmartCS-设计文档.md` v1.0  
**版本：** v1.0  
**日期：** 2026-05-20  
**测试基准：** 每日 1,000 张工单 / 80 名工程师 / 内网部署  

---

## 目录

1. [测试范围](#一测试范围)
2. [测试环境](#二测试环境)
3. [测试工具](#三测试工具)
4. [测试类别与策略](#四测试类别与策略)
5. [测试用例清单](#五测试用例清单)
6. [自动化测试脚本](#六自动化测试脚本)
7. [性能测试计划](#七性能测试计划)
8. [验收标准](#八验收标准)
9. [执行计划](#九执行计划)

---

## 一、测试范围

### 1.1 覆盖的需求模块

| 模块 | 需求章节 | 优先级 |
|------|---------|--------|
| 工单状态机（新） | 三、四 | P0 |
| 用户端全流程 | 四 | P0 |
| 工程师端全流程 | 五 | P1 |
| 管理后台 | 六 | P1 |
| AI/知识库 | 四 | P1 |
| 身份切换 | F-AGENT-14 | P1 |
| 语音消息+STT | F-USER-2b | P2 |
| 缺陷提交 | F-AGENT-8 | P1 |
| 问题升级 | F-AGENT-9 | P1 |
| 知识沉淀审核 | F-AGENT-10 | P1 |
| SSL 证书管理 | F-ADMIN-CONFIG-3 | P1 |
| 数据分析 | F-ADMIN-BIZ-7 | P1 |
| 归档策略 | 九 | P2 |
| 内网环境 | 一 | P2 |

### 1.2 覆盖的角色

| 角色 | 最低测试数 | 关键路径 |
|------|-----------|---------|
| 用户（注册） | 15-20 场景 | 注册→发消息→AI→转人工→评价→关闭 |
| 工程师（L1~L4） | 20-25 场景 | 登录→受理→回复→提请解决→关闭 |
| 管理员 | 15-20 场景 | 配置/业务/审计三大模块 |
| 系统（自动任务） | 5-8 场景 | 超时自动关闭/评价/归档 |

---

## 二、测试环境

### 2.1 环境配置

```
测试服务器：8.133.198.245 (Alibaba Cloud ECS)
操作系统：Ubuntu 22.04 LTS
运行时：Python 3.8+, SQLite WAL
数据库：/home/deploy/smart-cs/data/smartcs.db (独立测试数据库)
```

### 2.2 测试数据库准备

```bash
# 创建独立测试数据库
cp /home/deploy/smart-cs/data/smartcs.db /tmp/test_smartcs.db

# 设置测试环境变量
export SMART_CS_URL="http://localhost:8080"
export TEST_DB="/tmp/test_smartcs.db"
export TEST_MODE="1"  # 测试模式：缩短超时时长、跳过真实AI调用
```

### 2.3 测试数据基线

| 数据 | 数量 | 说明 |
|------|------|------|
| 注册用户 | 5+ | 含不同单位 |
| 工程师 | 4+ | L1-L4 各至少1人 |
| 系统清单 | 3+ | 不同报修系统 |
| 关单原因 | 5+ | 标准原因 |
| 工单 | 10+ | 覆盖所有状态 |
| 知识库文档 | 3+ | 含通过/待审核/驳回状态 |

---

## 三、测试工具

| 工具 | 用途 | 命令行 |
|------|------|--------|
| Python unittest/requests | 集成测试 | `python3 test_smartcs_full.py` |
| 新状态机测试脚本 | P0 核心验证 | `python3 test_state_machine.py` |
| wrk | HTTP 压力测试 | `wrk -t4 -c40 -d30s https://smartcs.internal/` |
| locust | 模拟并发用户 | `locust -f locustfile.py` |
| SQLite CLI | 数据状态验证 | `sqlite3 test.db "SELECT status, count(*) FROM tickets GROUP BY status"` |

---

## 四、测试类别与策略

### 4.1 单元测试（Unit Tests）

**目标：** 核心逻辑独立验证，覆盖率 > 70%  
**工具：** pytest  
**测试对象：**

| 模块 | 文件 | 测试数 |
|------|------|--------|
| 状态机 | `test_unit/test_state_machine.py` | ≥30 |
| STT 服务 | `test_unit/test_stt.py` | ≥5 |
| AI 引擎 | `test_unit/test_ai.py` | ≥5 |
| 适配器 | `test_unit/test_adapters.py` | ≥10 |
| 事件总线 | `test_unit/test_eventbus.py` | ≥5 |

### 4.2 集成测试（Integration Tests）

**目标：** 端到端全链路覆盖  
**工具：** Python requests (HTTP 原生) + 无框架断言  
**测试文件：** `tests/test_smartcs_full.py`（当前 62 项 → 扩展至 **100+ 项**）

**测试场景分层：**

```
Layer 1 — 基础功能（必须全部通过）
  A组: 系统可用性  (A1-A6)   ✅ 现有
  B组: 用户咨询    (B1-B4)   ✅ 现有 + 新增
  C组: 用户注册登录 (C1-C11)  ✅ 现有
  D组: 工程师流程   (D1-D17)  🔄 需重构（新状态机）
  E组: 管理后台     (E1-E17)  🔄 需扩展
  F组: 知识库      (F1)      需扩展
  G组: 边界条件    (G1-G4)   ✅ 现有

Layer 2 — 新功能（各里程碑新增）
  H组: 新状态机   (H1-H15)  全新
  I组: L1-L4级别   (I1-I5)   全新
  J组: 知识审核   (J1-J6)   全新
  K组: 身份切换   (K1-K4)   全新
  L组: 升级/缺陷  (L1-L4)   全新
  M组: 语音消息   (M1-M5)   全新
  N组: 数据分析   (N1-N6)   全新
  O组: 审计/归档  (O1-O5)   全新
  P组: SSL/配置   (P1-P4)   全新

Layer 3 — 回归测试（验证旧功能兼容）
  完整运行所有 Layer 1+2 用例
```

### 4.3 边界测试

| 场景 | 期望 | 优先级 |
|------|------|--------|
| 空消息内容 | 拒绝，不创建工单 | P0 |
| 超长消息 (>5000 字符) | 自动截断或拒绝 | P1 |
| 未登录访问工程师 API | 401 拒绝 | P0 |
| 工程师访问管理员 API | 403 拒绝 | P0 |
| 管理员越权操作 | 403 拒绝 | P1 |
| 同一工单重复关闭 | 拒绝 + 错误消息 | P1 |
| 已关闭工单发消息 | 拒绝或提示 | P1 |
| 同时转接多人 | 只允许一个受理 | P1 |
| 图片超过限制 (50MB) | 拒绝 | P2 |
| 语音文件格式不支持 | 拒绝 + 提示 | P2 |
| 超时调度精度 | ±30秒 | P0 |

### 4.4 性能测试

参见[第七节](#七性能测试计划)。

### 4.5 安全测试

| 测试项 | 工具/方法 | 预期 |
|--------|----------|------|
| XSS 注入 | 消息/用户名插入 `<script>alert(1)</script>` | 被转义或清除 |
| CSRF | 跨站 POST 请求 | 403 |
| SQL 注入 | 输入 `' OR 1=1--` | 查询安全 |
| 密码强度 | 弱密码 | 拒绝 |
| 会话劫持 | 篡改 Cookie | 无效 |
| 未授权 API 访问 | 无 Cookie 访问 | 401 或 302 |
| 越权 API 访问 | 用户 Cookie 访问工程师 API | 403 |

---

## 五、测试用例清单

### 5.1 Layer 1 — 基础功能（现有 62 项，保留 + 适配）

#### A组：系统可用性 (6项 ✅)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| A1 | 首页加载 | GET / | 200 + 包含聊天界面 |
| A2 | 登录页加载 | GET /login | 200 + 含登录表单 |
| A3 | 注册页可用 | POST /api/customer/register | 成功注册 |
| A4 | PWA manifest | GET /manifest.json | 返回正确配置 |
| A5 | Service Worker | GET /sw.js | 返回 SW 脚本 |
| A6 | 静态图标 | GET /icon-192.svg | 200 |

#### B组：用户咨询 (4项 ✅ → 扩展)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| B1 | 用户发消息→创建工单 | POST /api/chat | 返回 conversation_id ✅ |
| B2 | AI 自动回复 | 同 B1 响应 | reply 非空 ✅ |
| B3 | 转人工 | POST /api/customer/tickets/transfer | escalated=true ✅ |
| B4 | 对话历史 | GET /api/chat/history | 包含历史消息 ✅ |
| **B5** | **首次发消息→工单状态=created** | 新用户首次发消息 | 工单状态=created，ticket_id 非空 |
| **B6** | **注册用户≠游客** | 未注册用户发消息 | 拒绝 401 |
| **B7** | **已创建工单用户可见** | 用户查询工单列表 | 状态=created 的工单可见 |
| **B8** | **已创建工单工程师不可见** | 工程师查询待处理 | 不包含 created 工单 |

#### C组：用户注册/登录 (11项 ✅，不变)

保持 C1-C11 完全不变。

#### D组：工程师流程 (17项 🔄 重构适配新状态机)

| 编号 | 原用例 | 新状态机适配 |
|------|--------|-------------|
| D1 | 客服登录 ✅ | 不变 |
| D2 | 客服登出 ✅ | 不变 |
| D3 | 待处理工单列表 | 🔄 created 不可见，仅 processing |
| D4 | 我的工单列表 ✅ | 不变 |
| D5 | 历史工单列表 ✅ | 不变 |
| D6 | 查找待处理工单 | 🔄 按 processing 查找 |
| D7 | 受理工单 ✅ | 不变 |
| D8 | 客服加载对话 ✅ | 不变 |
| D9 | 客服查看工单详情 ✅ | 不变 |
| D10 | 客服发送回复 ✅ | 不变 |
| D11 | 用户收到客服回复 ✅ | 不变 |
| D12 | 客服提请处理完成 | 🔄 processing→resolved |
| D13 | 用户收到关闭提示 | 🔄 改为"处理完成提示" |
| D14 | 用户确认解决 | 🔄 resolved→rated |
| D15 | 用户评价服务 | 🔄 评价更新 rated 记录 |
| D16 | 客服最终关闭 | 🔄 rated→closed |
| D17 | 工单最终状态验证 | 🔄 verified 改为 closed |

#### E组：管理后台 (17项 ✅→🔄)

| E1-E17 | 基本不变 | 新增：知识审核、SSL、主题配置、仪表盘 |

### 5.2 Layer 2 — 新功能测试用例（全新编写）

#### H组：新状态机核心 (15项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **H1** | **全链路 happy path** | 用户发消息→AI→转人工→工程师受理→提请→用户评价→工程师关闭 | created→processing→resolved→rated→closed |
| **H2** | **created 超时自动关闭** | 创建工单后不操作，等待 auto_close_min | 自动 closed |
| **H3** | **resolved 超时自动评价** | 工程师提请完成后用户不操作，等待 auto_rate_hours | 自动 rated |
| **H4** | **管理员强制关闭任意状态** | 管理员调用强制关闭 | 状态→closed |
| **H5** | **已关闭工单不可操作** | 对 closed 工单发消息 | 拒绝 |
| **H6** | **同工单重复转人工** | 对 processing 工单调用 transfer | 拒绝或无变化 |
| **H7** | **unified close——L1-L4 均可关闭** | L1/L4 工程师各自关闭工单 | 全部成功 |
| **H8** | **unified close——不带 L1 直接关** | 不再有 L1 直接关路由 | 统一走提请流程 |
| **H9** | **超级管理员和普通管理员关单权限** | 管理员强制关闭 | 成功 |
| **H10** | **已处理状态用户可评价** | resolved 工单调用用户评价 | 成功→rated |
| **H11** | **已处理状态用户直接关闭（超时）** | resolved 超时不评价 | auto_rate → rated → 需工程师关闭 |
| **H12** | **created 工单向工程师隐藏** | 工程师 API 查询待处理 | 不包含 created |
| **H13** | **created 工单向用户可见** | 用户 API 查询工单列表 | 包含 created |
| **H14** | **状态变更系统消息** | 每次 transition 产生系统消息 | 包含 "工单状态已变更" |
| **H15** | **level_trace 记录** | 多级工程师经手后关闭 | level_trace 包含所有级别 |

#### I组：L1-L4 工程师级别 (5项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **I1** | **L1-L4 工程师都可登录** | 各等级工程师分别登录 | 成功 |
| **I2** | **L1-L4 权限相同** | 各等级工程师都操作受理/回复/提请/转交/关闭 | 全部有相同菜单 |
| **I3** | **级别在工单上可查** | 工单详情显示处理工程师级别 | 显示 |
| **I4** | **拦截率以最后关闭人级别为准** | L2→L3→关闭，level=3 | level_trace=[2,3], level=3 |
| **I5** | **管理员默认 L4（可配置）** | 管理员关闭后 level=4 | 除非管理员修改默认级别 |

#### J组：知识审核流程 (6项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **J1** | **工程师提交知识** | POST /api/agent/tickets/knowledge | status=pending |
| **J2** | **工程师查看自己提交** | GET /api/agent/knowledge/mine | 包含刚提交的 |
| **J3** | **管理员通过审核** | POST /api/admin/knowledge/{id}/approve | status=approved |
| **J4** | **已通过知识可被 AI 搜索** | AI 搜索包含新知识 | 命中 |
| **J5** | **管理员驳回知识** | POST /api/admin/knowledge/{id}/reject + reason | status=rejected±reason |
| **J6** | **被驳回知识可重提** | 工程师查看驳回原因→修改→重新提交 | 回到 pending |

#### K组：身份切换 (4项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **K1** | **工程师一键切换到用户模式** | 点击"切换到用户模式" | 跳转 chat.html，显示"🔁 用户模式" |
| **K2** | **切换模式下创建的工单 source 正确** | 切换后发消息 | 工单 source = 'engineer_impersonation' |
| **K3** | **一键切回工程师模式** | 点击顶栏"返回工程师工作台" | 回到 /agent/dashboard |
| **K4** | **统计中过滤身份切换来源** | 管理员查看来源分析 | engineer_impersonation 单独归类 |

#### L组：升级/缺陷 (4项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **L1** | **问题升级提交** | POST /api/agent/tickets/escalate | 通知管理层 |
| **L2** | **缺陷提交** | POST /api/agent/tickets/defect | 关联到缺陷系统 |
| **L3** | **缺陷状态查询** | GET /api/agent/tickets/defect-status | 返回状态 |
| **L4** | **升级目标可选** | 升级时选择目标（管理层/更高级别/特定负责人） | 正确通知 |

#### M组：语音消息 (5项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **M1** | **用户上传语音** | POST /api/chat/audio | 返回 audio_url |
| **M2** | **语音自动 STT 转文字** | 上传后查看消息 | stt_text 非空 |
| **M3** | **语音消息包含播放按钮和转写文字** | 前端渲染 | 显示 🔊 + 文字 |
| **M4** | **工程师也可以发语音** | POST /api/agent/reply（含 audio_url） | 成功发送 |
| **M5** | **管理员后台查看语音消息** | 管理员查工单详情 | 包含语音+转写文字 |

#### N组：数据分析 (6项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **N1** | **仪表盘概览** | GET /api/admin/stats/overview | 包含工单量趋势 |
| **N2** | **单位维度工单统计** | GET /api/admin/stats/companies | 按单位分组计数 |
| **N3** | **系统维度工单统计** | GET /api/admin/stats/systems | 按系统分组计数 |
| **N4** | **拦截率分析** | GET /api/admin/stats/interception | 按 level 分组，基于最后关闭人 |
| **N5** | **满意度统计** | 仪表盘含平均评分 | 正确计算 |
| **N6** | **来源分析** | 来源分布（web/engineer_impersonation/IM） | 分组正确 |

#### O组：审计/归档 (5项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **O1** | **操作审计含 IP** | 用户/工程师操作 | audit_log 含 ip_address |
| **O2** | **登录日志独立表** | POST /api/admin/login-logs | 成功返回 |
| **O3** | **IP 来源：X-Forwarded-For 优先** | 通过 Nginx 访问 | audit IP = X-Forwarded-For |
| **O4** | **IP 来源：fallback remote_addr** | 直接连接 | audit IP = remote_addr |
| **O5** | **归档定时任务** | 启动 /api/cron/archive | 超过 90 天的工单移入归档表 |

#### P组：SSL/配置 (4项)

| 编号 | 用例名 | 步骤 | 预期 |
|------|--------|------|------|
| **P1** | **配置项读写** | POST /api/admin/config（含所有新配置） | 保存成功，读取正确 |
| **P2** | **主题配置生效** | 修改 primary_color、logo_url | 前端页面刷新后生效 |
| **P3** | **SSL 证书上传** | POST /api/admin/config/ssl（PEM 文件） | 成功，Nginx reload |
| **P4** | **HTTPS 强制跳转** | HTTP 访问 | 301→HTTPS |

### 5.3 测试用例汇总

| 层级 | 现有 | 新增 | 总计 |
|------|------|------|------|
| Layer 1 基础 | 62 | — | 62 |
| Layer 2 新功能 | — | 59 | 59 |
| **总计** | **62** | **59** | **121** |

---

## 六、自动化测试脚本

### 6.1 脚本设计

**测试脚本结构：**

```
tests/
├── run_all.py              # 测试总入口，顺序执行所有 Layer
├── test_smartcs_full.py    # Layer 1: 基础功能 (62 项，现有适配)
├── test_state_machine.py   # Layer 2: 新状态机 (H组 15项，全新)
├── test_agent_features.py  # Layer 2: 工程师新功能 (I-J-K-L组 19项)
├── test_admin_features.py  # Layer 2: 管理员新功能 (N-O-P组 15项)
├── test_voice_messages.py  # Layer 2: 语音消息 (M组 5项)
├── test_edge_cases.py      # Layer 3: 边界条件 + 安全测试
└── locustfile.py           # 性能测试
```

### 6.2 核心测试脚本详解

#### 6.2.1 `test_smartcs_full.py`（Layer 1，保留并适配）

原有 62 项测试，需要做以下适配：

```python
# 改动1: D3 待处理工单列表 — 过滤掉 created 状态
# 之前：tickets with status in (open, assigned)
# 之后：tickets with status = 'processing'

# 改动2: D12 客服请求关闭 — processing→resolved（不再是直接关闭）
# 之前：POST /agent/tickets/close
# 之后：POST /agent/tickets/resolve

# 改动3: D14 用户确认解决 — resolved→rated
# 之前：POST /customer/confirm （同时关闭）
# 之后：POST /customer/tickets/confirm（仅评价，不关闭）

# 改动4: D16 客服关闭 — rated→closed
# 之前：无（D14已关闭）
# 之后：POST /agent/tickets/close

# 改动5: D17 状态验证 — 最后一个状态是 closed 而非 resolved
```

#### 6.2.2 `test_state_machine.py`（Layer 2，全新）

核心测试：验证状态机所有转移路径和超时逻辑。

**关键设计点：**

1. **测试模式缩短超时时长** — 设置 `auto_close_min=1`，`auto_rate_hours=0.017`(约1分钟) 来快速测试超时
2. **SQLite 直接验证** — 测试后直接查库确认状态
3. **层级 trace 验证** — 工单经手多级工程师后验证 `level_trace`

```python
#!/usr/bin/env python3
"""
SmartCS 新状态机集成测试脚本（H组 15项）
测试：created → processing → resolved → rated → closed
"""

import urllib.request, urllib.parse, json, uuid, time, re
import http.cookiejar

BASE = 'http://localhost:5000'
passed = 0
failed = 0

def test(name, ok, detail=''):
    # ... (同现有 test_smartcs_full.py 的 test 函数)

# 测试前：创建测试数据库，设置测试模式超时
# 将 auto_close_min 设为 1, auto_rate_hours 设为 0.017

# === H组：新状态机核心 ===

def run_state_machine_tests():
    """测试全部 15 项状态机场景"""
    
    # H1: Happy Path 全链路
    # 注册→发消息→查看工单(created)→转人工(processing)→
    # 工程师受理→提请完成(resolved)→用户评价(rated)→工程师关闭(closed)
    
    # H2: created 超时
    # 注册→发消息→等待 70 秒→查工单状态=closed
    
    # H3: resolved 超时  
    # ...完整流程直到 resolved→等待 70 秒→状态=rated
    
    # H4: 管理员强制关闭
    # 管理员登录→强制关闭 processing 工单→状态=closed
    
    # H5-H15: ...
```

#### 6.2.3 `test_agent_features.py`（Layer 2，全新）

```python
"""
工程师新功能测试（I-J-K-L组 19项）
- I组: L1-L4 级别权限
- J组: 知识审核流程
- K组: 身份切换
- L组: 升级/缺陷
"""
```

#### 6.2.4 `locustfile.py`（性能测试）

```python
from locust import HttpUser, task, between

class CustomerUser(HttpUser):
    wait_time = between(3, 10)
    
    def on_start(self):
        self.login()
    
    def login(self):
        resp = self.client.post("/api/customer/login", json={
            "email": "perf_test@test.com", "password": "Test123"
        })
    
    @task(5)
    def send_message(self):
        self.client.post("/api/chat", json={
            "conversation_id": self.conv_id,
            "message": "打印机无法使用，请求帮助"
        })
    
    @task(2)
    def chat_history(self):
        self.client.get("/api/chat/history")

class AgentUser(HttpUser):
    wait_time = between(5, 15)
    
    @task(3)
    def poll_tickets(self):
        self.client.get("/api/agent/tickets?tab=pending")
    
    @task(1)
    def send_reply(self):
        self.client.post("/api/agent/reply", json={...})
```

---

## 七、性能测试计划

### 7.1 测试场景

| 场景 | 负载 | 目标 | 工具 |
|------|------|------|------|
| 消息轮询 | 40 工程师并发，3s 间隔 | 响应 < 500ms | locust |
| 用户消息并发 | 50 用户同时发消息 | 响应 < 3s（含 AI） | wrk |
| 搜索 | 10 并发搜索 | 响应 < 500ms | wrk |
| 工单列表查询 | 20 并发查询 | 响应 < 300ms | wrk |
| 混合负载 | 40 工程师 + 50 用户 | 全部接口正常 | locust |
| 长时间运行 | 12 小时连续负载 | 无内存泄漏 | locust |

### 7.2 性能基准

| 接口 | 目标 P99 | 目标 P50 | 当前基准 |
|------|---------|---------|---------|
| POST /api/chat | <3s | <1s | ✅ |
| GET /api/agent/tickets | <500ms | <200ms | ✅ |
| GET /api/chat/history | <1s | <300ms | ✅ |
| POST /api/agent/reply | <500ms | <200ms | ✅ |
| POST /api/customer/tickets/confirm | <500ms | <200ms | ✅ |

### 7.3 测试数据生成

```python
# 生成 1000+ 工单、50000+ 消息用于性能测试
python3 scripts/generate_test_data.py \
  --tickets 1000 \
  --messages 50000 \
  --customers 50 \
  --agents 10
```

---

## 八、验收标准

### 8.1 测试通过标准

| 等级 | 要求 | 说明 |
|------|------|------|
| **Pass** | 全部 P0 用例通过 | 状态机核心功能可用 |
| **Conditional Pass** | P0 通过，P1 通过 ≥90% | 可上线试运行 |
| **Fail** | 任何 P0 用例失败 | 不可上线 |

### 8.2 质量门禁

```
Commit 阶段: → 集成测试（全部 pass）
    ↓
PR Merge 阶段: → 集成测试 + 单元测试（全部 pass）
    ↓
Pre-release: → 集成测试 + 性能测试（P0+P1 pass, 性能达标）
    ↓
Release: → 全量回归测试（121 pass）
```

### 8.3 覆盖率目标

| 类型 | 当前 | 目标 |
|------|------|------|
| 集成测试数量 | 62 | ≥120 |
| 状态机覆盖率 | — | 100%（所有状态转移至少一次） |
| API 端点覆盖率 | ~60% | ≥90% |
| 边界测试 | ~5% | ≥20% |
| 安全测试 | 0 | ≥10 场景 |

---

## 九、执行计划

### Phase 0: 基础设施（1 天）

- [ ] 准备独立测试数据库
- [ ] 编写 `run_all.py` 测试总入口
- [ ] 创建 `scripts/generate_test_data.py` 数据生成器
- [ ] 设置 CI (GitHub Actions / 内网 GitLab CI)

### Phase 1: P0 核心测试（2 天，同步状态机开发）

- [ ] 适配现有 test_smartcs_full.py（D组 17项）
- [ ] 编写 test_state_machine.py（H组 15项）
- [ ] 验证：全链路 happy path + 超时 + 边界

### Phase 2: P1 功能测试（2 天，同步 P1 开发）

- [ ] 编写 test_agent_features.py（I,J,K,L组 19项）
- [ ] 编写 test_admin_features.py（N,O,P组 15项）
- [ ] 验证：L1-L4、知识审核、身份切换、仪表盘、SSL

### Phase 3: P2+ 测试（1 天）

- [ ] 编写 test_voice_messages.py（M组 5项）
- [ ] 安全测试（XSS/SQL注入/CSRF/越权）
- [ ] 编写 locustfile.py 性能测试
- [ ] 12 小时负载测试

---

**版本：** v1.0  
**关联：** `docs/SmartCS-需求文档.md`、`docs/SmartCS-设计文档.md`  
**测试引擎负责人：** 旺财
