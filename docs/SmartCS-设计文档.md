# SmartCS 智能客服工单系统 — 设计文档

**关联需求文档：** `docs/SmartCS-需求文档.md` v5.6  
**版本：** v1.0  
**日期：** 2026-05-20  
**设计基准：** 每日 1,000 张工单 / 80 名工程师 / 内网部署  

---

## 目录

1. [总体架构设计](#一总体架构设计)
2. [模块设计](#二模块设计)
3. [状态机设计](#三状态机设计)
4. [数据库设计](#四数据库设计)
5. [API 设计](#五-api-设计)
6. [前端设计](#六前端设计)
7. [安全设计](#七安全设计)
8. [硬件资源需求](#八硬件资源需求)
9. [软件资源需求](#九软件资源需求)
10. [部署架构](#十部署架构)
11. [开发实施路线图](#十一开发实施路线图)
12. [测试策略](#十二测试策略)

---

## 一、总体架构设计

### 1.1 架构视图

```
┌──────────────────────────────────────────────────────────────────┐
│                       内网网络                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   客户端                                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ 用户浏览器 │  │工程师浏览器│  │管理员浏览器│              │   │
│  │  │ (PWA)    │  │ (PWA)    │  │ (桌面)   │              │   │
│  │  └─────┬────┘  └────┬─────┘  └────┬─────┘              │   │
│  └────────┼────────────┼─────────────┼──────────────────────┘   │
│           │            │             │                           │
│           ▼            ▼             ▼                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Nginx 反向代理（HTTPS）                      │   │
│  │    ssl_cert: /etc/nginx/certs/smartcs.pem                │   │
│  │    80 → 443 强制跳转                                     │   │
│  └─────────────────────┬────────────────────────────────────┘   │
│                        │                                         │
│                        ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Gunicorn (3-4 workers)                       │   │
│  │              Flask 应用 (app.py)                          │   │
│  │                                                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │ 工单引擎  │ │ 消息引擎  │ │ AI 网关  │ │ 集成适配器  │  │   │
│  │  │ (状态机)  │ │ (轮询)   │ │ (LLM)   │ │ (Auth/IM)  │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬─────┘  │   │
│  └───────┼────────────┼────────────┼───────────────┼────────┘   │
│          │            │            │               │             │
│          ▼            ▼            ▼               ▼             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              数据层                                         │   │
│  │  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ SQLite (WAL) │  │ 本地磁盘  │  │ 备份目录          │    │   │
│  │  │ smartcs.db   │  │ uploads/ │  │ /backup/smartcs/ │    │   │
│  │  │              │  │ audio/   │  │ (每日+WAL增量)   │    │   │
│  │  └──────────────┘  └──────────┘  └──────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              内部服务（可选 / 按需部署）                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ LLM 服务  │  │ Whisper  │  │ LDAP/AD  │              │   │
│  │  │ Ollama/  │  │ (STT)   │  │ (认证)   │              │   │
│  │  │ vLLM     │  │ :9090   │  │ :389     │              │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 架构模式

| 模式 | 选型 | 理由 |
|------|------|------|
| 应用架构 | 单体 Flask（模块化组织） | 1,000 单/天 + 80 工程师，单体足够；模块拆分用子目录而非微服务 |
| 适配器模式 | Auth / IM / 外部服务 | 统一接口，插拔式切换本地/云端实现 |
| 状态机模式 | 工单状态流转 | 有限状态机，状态+事件驱动 |
| 仓库模式 | app.py 分层 | 当前 3620 行需按功能拆分多个文件 |
| 观察者模式 | 事件总线 + Webhook | 系统状态变更时通知外部系统 |

### 1.3 代码组织（重构目标）

```
smartcs/
├── app.py                  # 应用入口 + 路由注册 + 启动
├── config.py               # 配置读取（system_config 表）
├── models.py               # 数据库模型 + CRUD 基类
├── state_machine.py        # 工单状态机核心
├── routes/
│   ├── __init__.py
│   ├── customer.py         # 用户端 API
│   ├── agent.py            # 工程师端 API
│   ├── admin.py            # 管理后台 API
│   ├── auth.py             # 认证相关 API
│   └── integration.py      # 集成网关 API
├── services/
│   ├── ticket_service.py   # 工单业务逻辑
│   ├── message_service.py  # 消息业务逻辑
│   ├── ai_service.py       # AI 引擎（LLM 适配）
│   ├── stt_service.py      # 语音识别（Whisper 适配）
│   └── knowledge_service.py# 知识库搜索
├── adapters/
│   ├── auth/               # 认证适配器
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── ldap.py
│   │   └── oidc.py
│   ├── im/                 # IM 通道适配器
│   │   ├── base.py
│   │   ├── wecom.py
│   │   └── dingtalk.py
│   └── external/           # 外部服务适配器
│       ├── base.py
│       ├── jira.py
│       └── zentao.py
├── templates/
├── static/
├── tests/
│   ├── test_full.py        # 62 项集成测试
│   └── test_unit/          # 单元测试目录（待补充）
├── scripts/
│   ├── deploy.sh           # 一键部署脚本
│   ├── init_db.py          # 数据库初始化+迁移
│   └── gen_cert.sh         # 自签证书生成
├── docs/
│   ├── SmartCS-需求文档.md
│   └── SmartCS-设计文档.md
├── data/                   # 运行时数据
├── uploads/                # 用户上传文件
├── knowledge/              # 知识库文件
├── requirements.txt
└── README.md
```

---

## 二、模块设计

### 2.1 工单引擎模块（核心）

**职责：** 工单创建、状态流转、超时调度

```
┌─────────────────────────────────────────┐
│           工单引擎 TicketEngine          │
│                                         │
│  create(user_id) → ticket (created)      │
│  transfer(ticket, user) → processing     │
│  assign(ticket, agent) → processing      │
│  transfer_to(ticket, from, to) → assigned│
│  resolve(ticket, agent) → resolved       │
│  rate(ticket, user) → rated             │
│  close(ticket, agent) → closed          │
│  force_close(ticket, admin) → closed    │
│  escalate(ticket, agent) → escalated     │
│                                         │
│  定时任务:                               │
│  auto_close_expired()                    │
│  auto_rate_expired()                     │
│  archive_old_tickets()                   │
└─────────────────────────────────────────┘
```

**关键接口：**

```python
class TicketEngine:
    def create(customer_id: str, conversation_id: str) -> Ticket
    def transfer_to_human(ticket_id: str) -> Ticket  # created → processing
    def assign(ticket_id: str, agent_id: str) -> Ticket
    def propose_resolution(ticket_id: str, agent_id: str) -> Ticket  # processing → resolved
    def confirm_and_rate(ticket_id: str, rating: int, feedback: str) -> Ticket  # resolved → rated
    def close(ticket_id: str, agent_id: str, reason: str, notes: str) -> Ticket  # rated → closed
    def force_close(ticket_id: str, admin_id: str, reason: str) -> Ticket  # any → closed
    def auto_close(expire_minutes: int) -> List[Ticket]  # 定时任务
    def auto_rate(expire_hours: int) -> List[Ticket]  # 定时任务
```

### 2.2 消息引擎模块

**职责：** 消息收发、轮询、图片/语音上传

```python
class MessageEngine:
    def send(sender_id, conversation_id, content, msg_type, 
             image_url=None, audio_url=None, stt_text=None)
    def send_system(ticket_id, content)  # 系统消息（状态变更通知）
    def poll_messages(conversation_id, since_id)  # 3s 轮询
    def upload_image(file) -> url       # 用户/工程师均可上传
    def upload_audio(file) -> url       # 用户/工程师均可上传
    def stt_transcribe(audio_path) -> str  # 调用 Whisper（内置）
```

### 2.3 AI 引擎模块

**职责：** 知识库检索、LLM 对话、本地模型适配

```python
class AIEngine:
    def __init__(self):
        self.api_base = config('ai_api_base_url')  # 支持内网 Ollama/vLLM
        self.model = config('ai_model_name')
    
    def chat(conversation_id, user_message) -> str
    def search_knowledge(query) -> List[Document]
    def suggest_human(query) -> bool  # AI 无法回答时返回 True
```

**内网 LLM 适配：** 兼容 OpenAI API 格式，只需配置 `ai_api_base_url` 指向内网地址：

```python
# Ollama 示例
ai_api_base_url = "http://10.0.0.10:11434/v1"
ai_model_name = "qwen2.5:14b"

# vLLM 示例
ai_api_base_url = "http://10.0.0.10:8000/v1"
ai_model_name = "Qwen/Qwen2.5-14B-Instruct"
```

### 2.4 语音识别模块（STT）

**职责：** 语音→文字转换，对接 AI 或客服。用户和工程师均可发送语音消息。

#### 内置 STT 引擎选型（内网友好，无需云端 API）

| 方案 | 部署 | CPU 可用 | GPU 加速 | 中文质量 | 推荐场景 |
|------|------|---------|---------|---------|---------|
| **faster-whisper** | `pip install faster-whisper` | ✅ small 模型 | ✅ CUDA | ⭐⭐⭐⭐ | **默认推荐** |
| **whisper.cpp** | 编译安装 | ✅✅ 极快 | ✅ | ⭐⭐⭐⭐ | **低资源首选** (1-2核) |
| openai-whisper | pip install | ⚠️ 慢 | ✅ | ⭐⭐⭐⭐⭐ | 有 GPU 机器 |
| FunASR (阿里) | pip install | ✅ | ✅ | ⭐⭐⭐⭐⭐ | 中文专项优化 |

```python
class STTService:
    def __init__(self):
        self.engine = config('stt_engine')   # 'faster_whisper' | 'whisper_cpp' | 'openai_whisper' | 'cloud_api'
        self.model_size = config('stt_model_size', 'small')  # tiny|base|small|medium|large
        self.language = config('stt_language', 'zh')          # zh|en|auto
    
    def transcribe(audio_path: str) -> TranscriptionResult
        # faster-whisper: faster_whisper.WhisperModel(model_size, device)
        # whisper.cpp: subprocess whisper-cli --file ...
        # cloud: 配置的 ASR API
    
    def transcribe_async(audio_path: str, callback_url: str)
        # 异步模式：大文件或批量场景
```

#### 语音消息处理流程（用户+工程师双向）：

```
     用户录音        工程师录音
        │                │
        ▼                ▼
   ┌──────────────────────────┐
   │   .webm 文件上传          │
   └──────────┬───────────────┘
              │
              ▼
   ┌──────────────────────────┐
   │   内置 STT 引擎           │
   │   (faster-whisper /       │
   │    whisper.cpp)           │
   │   本地运行，无需联网       │
   └──────────┬───────────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
 用户AI阶段  用户已转   工程师回复
  (created)  人工       用户
    │        (proc.)      │
    ▼         ▼           ▼
 AI搜索     文本消息    文本消息
 AI回复     +语音按钮   +语音按钮
           →工程师     →用户
```

**配置项（管理后台→配置管理→语音识别）：**

| key | 默认值 | 可选值 |
|-----|--------|--------|
| `stt_engine` | `faster_whisper` | `faster_whisper` / `whisper_cpp` / `openai_whisper` / `cloud_api` |
| `stt_model_size` | `small` | `tiny` / `base` / `small` / `medium` / `large` |
| `stt_language` | `zh` | `zh` / `en` / `auto` |
| `stt_gpu` | `false` | `true` / `false`（有 GPU 时自动启用） |
| `asr_api_key` | `''` | cloud_api 模式时使用 |
| `asr_api_url` | `''` | cloud_api 模式时使用 |

### 2.5 知识库模块

**职责：** 知识文档管理、FTS5 搜索、审核流程

```python
class KnowledgeService:
    def search(query) -> List[Document]       # FTS5 全文搜索
    def upload(file, submitter_id) -> Doc     # 状态 = pending
    def approve(doc_id, admin_id) -> Doc      # pending → approved
    def reject(doc_id, admin_id, reason)      # pending → rejected
    def list_by_status(status) -> List[Doc]
    def list_by_submitter(submitter_id) -> List[Doc]
```

**审核流程状态：**
```
工程师提交 → pending ──┬── 管理员通过 → approved → AI 可搜索
                       └── 管理员驳回 → rejected → 工程师可修改重提
```

### 2.6 集成网关模块

**职责：** 事件总线、适配器管理、Webhook 投递

```
事件源                       事件总线                      消费者
──────                      ────────                      ──────
工单引擎 ── ticket.created ──►                       ──► Webhook（外部系统）
消息引擎 ── ticket.rated   ──►  EventBus.emit()     ──► IM 通知
审计模块 ── ticket.closed  ──►                       ──► 内部日志
         ── agent.reply    ──►
```

---

## 三、状态机设计

### 3.1 状态定义

```python
class TicketState:
    CREATED     = 'created'      # 已创建：用户首次发消息
    PROCESSING  = 'processing'   # 处理中：工程师已受理
    RESOLVED    = 'resolved'     # 已处理：工程师提请完成
    RATED       = 'rated'        # 已评价：用户已评价或超时
    CLOSED      = 'closed'       # 已关闭：工程师或管理员关闭
```

### 3.2 状态转移矩阵

| 当前状态 \ 事件 | 转人工 | 受理 | 提请处理完成 | 确认+评价 | 超时自动评价 | 关闭工单 | 管理员强制关闭 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **created** | processing | — | — | — | closed | — | closed |
| **processing** | — | — | resolved | — | — | — | closed |
| **resolved** | — | — | — | rated | rated | — | closed |
| **rated** | — | — | — | — | — | closed | closed |
| **closed** | — | — | — | — | — | — | — |

### 3.3 状态机核心实现

```python
TRANSITIONS = {
    TicketState.CREATED: {
        'transfer': TicketState.PROCESSING,
        'timeout':  TicketState.CLOSED,       # auto_close_min
        'force':    TicketState.CLOSED,
    },
    TicketState.PROCESSING: {
        'resolve':  TicketState.RESOLVED,
        'force':    TicketState.CLOSED,
    },
    TicketState.RESOLVED: {
        'rate':     TicketState.RATED,
        'timeout':  TicketState.RATED,         # auto_rate_hours
        'force':    TicketState.CLOSED,
    },
    TicketState.RATED: {
        'close':    TicketState.CLOSED,
        'force':    TicketState.CLOSED,
    },
    TicketState.CLOSED: {},  # 终态
}

def transition(ticket, event, actor_id, **kwargs):
    allowed = TRANSITIONS.get(ticket.status, {})
    new_status = allowed.get(event)
    if not new_status:
        raise InvalidTransition(f"{ticket.status} → {event} 不允许")
    # 执行状态变更
    ticket.status = new_status
    # 审计日志
    log_audit(ticket.id, f"ticket.{event}", actor_id)
    # 事件总线
    event_bus.emit(f"ticket.{new_status}", ticket_id=ticket.id)
    return ticket
```

### 3.4 超时调度

```python
# 定时任务：每分钟执行
def check_timeouts():
    now = datetime.now()
    
    # 1. created → closed（超时自动关闭）
    auto_close_min = int(config('auto_close_min', '20'))
    expired_created = Ticket.select().where(
        Ticket.status == TicketState.CREATED,
        Ticket.updated_at < now - timedelta(minutes=auto_close_min)
    )
    for t in expired_created:
        transition(t, 'timeout', 'system')
    
    # 2. resolved → rated（超时自动已评价）
    auto_rate_hours = int(config('auto_rate_hours', '24'))
    expired_resolved = Ticket.select().where(
        Ticket.status == TicketState.RESOLVED,
        Ticket.updated_at < now - timedelta(hours=auto_rate_hours)
    )
    for t in expired_resolved:
        transition(t, 'timeout', 'system')
```

---

## 四、数据库设计

### 4.1 核心表结构

#### service_tickets（工单主表）

```sql
CREATE TABLE service_tickets (
    id              TEXT PRIMARY KEY,           -- UUID
    conversation_id TEXT NOT NULL,              -- 关联会话
    customer_id     TEXT NOT NULL,              -- 用户
    agent_id        TEXT,                       -- 当前处理工程师
    status          TEXT NOT NULL DEFAULT 'created',  -- created|processing|resolved|rated|closed
    ticket_number   TEXT DEFAULT '',            -- 编号 tk20260518000001
    issue_description TEXT DEFAULT '',          -- 问题描述
    priority        TEXT DEFAULT 'normal',      -- normal|urgent
    level           INTEGER DEFAULT 1,          -- 最终关闭级别 (1-4)
    
    -- 时间记录
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    updated_at      TEXT DEFAULT (datetime('now','localtime')),
    assigned_at     TEXT,
    resolved_at     TEXT,
    rated_at        TEXT,
    closed_at       TEXT,
    
    -- 评价
    customer_rating    INTEGER DEFAULT 0,       -- 1-5
    customer_feedback  TEXT DEFAULT '',
    
    -- 关闭信息
    close_reason     TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    admin_remarks    TEXT DEFAULT '',
    
    -- 流转追踪
    transferred_from TEXT DEFAULT '',
    first_read_at    TEXT DEFAULT '',
    reopened_at      TEXT DEFAULT '',
    reopened_count   INTEGER DEFAULT 0,
    
    -- 其他
    image_url        TEXT DEFAULT '',
    level_trace      TEXT DEFAULT '[]'           -- JSON: 经过的所有工程师级别
);
CREATE INDEX idx_tickets_status ON service_tickets(status);
CREATE INDEX idx_tickets_customer ON service_tickets(customer_id);
CREATE INDEX idx_tickets_agent ON service_tickets(agent_id);
CREATE INDEX idx_tickets_created ON service_tickets(created_at);
CREATE INDEX idx_tickets_number ON service_tickets(ticket_number);
```

> **新增字段：** `level_trace` 记录工单经过的所有工程师级别，用于拦截率计算。格式 `[1, 2, 3]`。

#### tickets_archive（归档表）

结构与 `service_tickets` 一致，增加 `archived_at` 字段。按 `created_at` 分区索引。

#### customers（用户主表）

```sql
CREATE TABLE customers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT DEFAULT '',
    password_hash   TEXT DEFAULT '',
    contact         TEXT DEFAULT '',
    source          TEXT DEFAULT 'web',
    company         TEXT DEFAULT '',            -- 所在单位/公司
    department      TEXT DEFAULT '',
    employee_id     TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

#### agents（工程师主表）

```sql
CREATE TABLE agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT,
    password_hash   TEXT NOT NULL,
    status          TEXT DEFAULT 'offline',     -- online|offline|busy
    role            TEXT DEFAULT 'agent',       -- agent|admin
    max_concurrent  INTEGER DEFAULT 5,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE agent_profiles (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT,
    display_name    TEXT DEFAULT '',
    department      TEXT DEFAULT '',
    title           TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    employee_id     TEXT DEFAULT '',
    company         TEXT DEFAULT '',
    agent_level     INTEGER DEFAULT 1           -- 1|2|3|4
);
```

#### messages（消息表）

```sql
CREATE TABLE messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,              -- user|bot|agent|system
    content         TEXT NOT NULL,
    msg_type        TEXT DEFAULT 'text',        -- text|image|audio|system
    image_url       TEXT DEFAULT '',
    audio_url       TEXT DEFAULT '',
    stt_text        TEXT DEFAULT '',            -- 语音转写文字
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_messages_conv ON messages(conversation_id);
```

#### knowledge_files（知识库）

```sql
CREATE TABLE knowledge_files (
    id              TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    content         TEXT DEFAULT '',             -- 文档内容（FTS5 索引）
    word_count      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',      -- pending|approved|rejected
    submitter_id    TEXT DEFAULT '',             -- 提交工程师 ID
    reject_reason   TEXT DEFAULT '',             -- 驳回原因
    uploaded_by     TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
-- FTS5 全文搜索索引
CREATE VIRTUAL TABLE knowledge_fts USING fts5(content, content=knowledge_files);
```

#### login_logs（登录日志，审计用）

```sql
CREATE TABLE login_logs (
    id              TEXT PRIMARY KEY,
    account_type    TEXT NOT NULL,              -- customer|agent|admin
    account_id      TEXT NOT NULL,
    ip_address      TEXT DEFAULT '',
    user_agent      TEXT DEFAULT '',
    status          TEXT NOT NULL,              -- success|failure|logout
    fail_reason     TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_login_logs_account ON login_logs(account_id);
CREATE INDEX idx_login_logs_time ON login_logs(created_at);
```

#### audit_log（审计日志，增强）

```sql
-- 现有字段不变，新增：
-- ip_address TEXT DEFAULT ''
```

### 4.2 system_config 新增配置项

| key | 默认值 | 说明 |
|-----|--------|------|
| `auto_close_min` | `20` | 已创建超时自动关闭（分钟） |
| `auto_rate_hours` | `24` | 已处理用户未确认自动评价（小时） |
| `archive_after_days` | `90` | 工单归档天数 |
| `ticket_search_max_days` | `365` | 工程师可搜索最大时间范围（天） |
| `stt_engine` | `whisper_local` | 语音识别引擎 |
| `ai_api_base_url` | (已存在) | AI 引擎地址，指向内网 LLM |
| `audit_retention_days` | `180` | 审计日志保留天数 |
| `theme_primary_color` | `#1890ff` | 主题色 |
| `theme_logo_url` | `''` | Logo 地址 |
| `theme_brand_name` | `SmartCS` | 品牌名称 |
| `theme_dark_mode` | `false` | 深色模式开关 |

### 4.3 数据迁移方案（从旧状态机到新状态机）

```sql
-- 旧 → 新 状态映射
UPDATE service_tickets SET status = 'processing' WHERE status IN ('open', 'assigned');
UPDATE service_tickets SET status = 'resolved'   WHERE status = 'confirmed';
UPDATE service_tickets SET status = 'closed'     WHERE status IN ('resolved', 'closed');
```

---

## 五、API 设计

### 5.1 用户端 API

| 方法 | 路径 | 说明 | 对应需求 |
|------|------|------|---------|
| POST | `/api/customer/register` | 注册 | F-USER-4 |
| POST | `/api/customer/login` | 登录 | F-USER-4 |
| POST | `/api/customer/logout` | 登出 | F-USER-4 |
| GET | `/api/customer/me` | 当前用户信息 | F-USER-4 |
| GET | `/api/customer/profile` | 个人资料 | F-USER-5 |
| POST | `/api/customer/profile` | 更新资料 | F-USER-5 |
| POST | `/api/chat` | 发消息（首次自动创建工单） | F-USER-1 |
| GET | `/api/chat/history` | 对话历史 | F-USER-1 |
| POST | `/api/chat/upload` | 上传图片 | F-USER-2 |
| POST | `/api/chat/audio` | **上传语音** | F-USER-2b |
| POST | `/api/customer/tickets` | 工单列表 | F-USER-6 |
| POST | `/api/customer/tickets/confirm` | 确认+评价 (resolved→rated) | F-USER-6 |
| POST | `/api/customer/tickets/search` | 搜索工单 | F-USER-7 |
| POST | `/api/customer/tickets/transfer` | 转人工 (created→processing) | F-USER-3 |
| POST | `/api/conversation/auto-close` | 空闲超时处理 | — |

### 5.2 工程师端 API

| 方法 | 路径 | 说明 | 对应需求 |
|------|------|------|---------|
| POST | `/agent/login` | 登录 | F-AGENT-1 |
| POST | `/agent/logout` | 登出 | F-AGENT-1 |
| GET | `/api/agent/tickets` | 工单列表（4标签） | F-AGENT-2 |
| POST | `/api/agent/tickets/assign` | 受理工单 | F-AGENT-3 |
| POST | `/api/agent/tickets/resolve` | **提请处理完成** (processing→resolved) | F-AGENT-5 |
| POST | `/api/agent/tickets/close` | **关闭工单** (rated→closed) | F-AGENT-5 |
| POST | `/api/agent/tickets/transfer` | 转交 | F-AGENT-4 |
| GET | `/api/agent/tickets/transfer-agents` | 可转交列表 | F-AGENT-4 |
| POST | `/api/agent/tickets/escalate` | **问题升级** | F-AGENT-9 |
| POST | `/api/agent/tickets/defect` | **缺陷提交** | F-AGENT-8 |
| GET | `/api/agent/tickets/defect-status` | 缺陷状态查询 | F-AGENT-8 |
| POST | `/api/agent/tickets/knowledge` | **知识沉淀** (提交) | F-AGENT-10 |
| GET | `/api/agent/knowledge/mine` | 我提交的知识文档 | F-AGENT-10 |
| POST | `/api/agent/reply` | 回复消息 | F-AGENT-3 |
| GET | `/api/agent/conversation/<id>` | 获取对话 | F-AGENT-3 |
| GET | `/api/agent/customers` | 客户列表 | — |
| GET | `/api/agent/profile` | 个人资料 | — |
| POST | `/api/agent/profile` | 更新资料 | — |
| POST | `/api/agent/switch-mode` | **身份切换** (工程师→用户) | F-AGENT-14 |
| GET | `/api/agent/tickets/search` | **按时间段搜索** | F-AGENT-2 |

### 5.3 管理后台 API

| 方法 | 路径 | 说明 | 模块 |
|------|------|------|------|
| **配置管理** | | | |
| GET/POST | `/api/admin/config` | 所有配置项读写 | CONFIG-1 |
| POST | `/api/admin/config/ssl` | SSL 证书上传 | CONFIG-2 |
| GET/POST | `/api/admin/config/theme` | 主题配置 | CONFIG-4 |
| CRUD | `/api/admin/im-adapters` | IM 适配器 | CONFIG-2 |
| CRUD | `/api/admin/external-adapters` | 外部适配器 | CONFIG-2 |
| CRUD | `/api/admin/webhooks` | Webhook | CONFIG-2 |
| CRUD | `/api/admin/auth-providers` | 认证提供者 | CONFIG-2 |
| **业务管理** | | | |
| CRUD | `/api/admin/customers` | 用户管理 | BIZ-1 |
| CRUD | `/api/admin/agents` | 工程师管理 | BIZ-1 |
| GET | `/api/admin/tickets` | 工单列表 | BIZ-2 |
| PUT | `/api/admin/tickets/<id>/status` | **工单状态干预** | BIZ-2 |
| DELETE | `/api/admin/tickets/<id>` | 删除工单 | BIZ-2 |
| CRUD | `/api/admin/close-reasons` | 关单类型 | BIZ-3 |
| CRUD | `/api/admin/systems` | 系统清单 | BIZ-4 |
| CRUD | `/api/admin/knowledge` | 知识库管理 | BIZ-5 |
| POST | `/api/admin/knowledge/<id>/approve` | **知识审核通过** | BIZ-5 |
| POST | `/api/admin/knowledge/<id>/reject` | **知识审核驳回** | BIZ-5 |
| GET | `/api/admin/stats/overview` | 仪表盘概览 | BIZ-7 |
| GET | `/api/admin/stats/agents` | 工程师绩效 | BIZ-7 |
| GET | `/api/admin/stats/interception` | **拦截率分析** | BIZ-7 |
| GET | `/api/admin/stats/systems` | 系统维度统计 | BIZ-7 |
| GET | `/api/admin/stats/companies` | 单位维度统计 | BIZ-7 |
| GET | `/api/admin/tickets/export` | 条目化导出 | BIZ-10 |
| **审计管理** | | | |
| GET | `/api/admin/audit-logs` | 操作审计日志（含IP） | AUDIT-1 |
| GET | `/api/admin/login-logs` | **登录记录** | AUDIT-2 |
| POST | `/api/admin/audit/archive` | 日志归档 | AUDIT-3 |

### 5.4 集成网关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/im/callback/<adapter_id>` | IM 回调入口（企微/钉钉） |
| POST | `/api/im/notify` | IM 通知 |
| GET | `/api/auth/providers-enabled` | 已启用的认证提供者 |
| POST | `/api/auth/ldap/login` | LDAP 登录 |
| GET | `/api/auth/oidc/login/<provider_id>` | OIDC 登录跳转 |
| GET | `/agent/oidc/callback` | OIDC 回调 |

---

## 六、前端设计

### 6.1 页面路由

| URL | 页面 | 角色 | 对应模板 |
|-----|------|------|---------|
| `/` | 用户咨询首页 | 用户 | `chat.html` |
| `/login` | 用户登录/注册 | 用户 | `chat.html`（内嵌） |
| `/register` | 用户注册 | 用户 | `chat.html`（内嵌） |
| `/user/login` | 独立登录页 | 用户 | `user_login.html`（备用） |
| `/agent/login` | 工程师登录 | 工程师 | `agent_login.html` |
| `/agent/dashboard` | 工程师工作台 | 工程师 | `agent_dashboard.html` |
| `/admin/dashboard` | 管理后台 | 管理员 | `admin.html` |
| `/upload` | 知识库管理 | 管理员 | `upload.html` |
| `/manifest.json` | PWA 清单 | 所有 | — |
| `/sw.js` | Service Worker | 所有 | — |

### 6.2 工程师工作台（agent_dashboard）布局

```
┌─────────────────────────────────────────────────────────┐
│  [Logo] SmartCS 工程师工作台  [在线] [切换到用户模式] [头像] │
├──────────────────────────┬──────────────────────────────┤
│  ┌─ 工单管理 ──────────┐ │ ┌─ 对话区 ────────────────┐ │
│  │ [待处理] [已处理]     │ │ │  用户: xxx              │ │
│  │ [全部经手] [🔍搜索]  │ │ │  ─────────────────────  │ │
│  │                      │ │ │  消息气泡...            │ │
│  │  ┌─ 工单列表 ────┐   │ │ │  消息气泡...            │ │
│  │  │ #123 L2 打印机 │   │ │ │                        │ │
│  │  │ #124 L1 网络  │   │ │ ├────────────────────────┤ │
│  │  │ #125 L3 系统  │   │ │ │ [输入框] [📷] [🎤] [发送]│ │
│  │  └────────────────┘   │ │ └────────────────────────┘ │
│  │                        │ │                          │ │
│  │  按钮：提交缺陷 沉淀知识│ │  操作：[提请处理完成]     │ │
│  │  升级问题 转交 关闭     │ │       [转交] [关闭]      │ │
│  └────────────────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 6.3 用户端（chat.html）布局

```
┌─────────────────────────────────────────┐
│  [菜单] SmartCS  [👤 昵称 ✓ 已登录]     │
├─────────────────────────────────────────┤
│  ┌─ 个人信息 ─────────────────────────┐ │
│  │  👤 我的信息  📋 我的报修           │ │
│  │  🔍 搜索工单  🚪 退出              │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌─ 我的工单 ─────────────────────────┐ │
│  │  #125 打印机故障 ... 处理中         │ │
│  │  #124 网络问题 ... 已评价           │ │
│  │  [查看全部 →]                      │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌─ 对话区 ───────────────────────────┐ │
│  │  AI: 您好，请问有什么可以帮助您？   │ │
│  │  用户: 打印机无法连接              │ │
│  │  AI: [知识库搜索结果...]           │ │
│  │  AI: 如果以上未解决，[转人工]      │ │
│  │  ...                               │ │
│  ├────────────────────────────────────┤ │
│  │ [输入框] [📷] [🎤] [发送]          │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 6.4 PWA 配置

```json
{
  "name": "SmartCS",
  "short_name": "SmartCS",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1890ff",
  "icons": [{ "src": "/icon-192.svg", "sizes": "192x192", "type": "image/svg+xml" }]
}
```

通过管理后台配置覆盖 `theme_color` 和 `name`。

---

## 七、安全设计

### 7.1 认证方案（分阶段）

| 阶段 | 用户端 | 工程师端 | 管理端 |
|------|--------|---------|--------|
| **当前** | 邮箱+密码 (SHA256) | 邮箱+密码 (SHA256) | 管理员账号 |
| **P1 改造** | 邮箱+密码 (bcrypt) | 邮箱+密码 (bcrypt) + LDAP/OIDC | 管理员+bcrpyt |
| **远期** | SSO (OIDC/LDAP) | LDAP/OIDC | LDAP/OIDC |

### 7.2 审计日志覆盖范围

| 操作类别 | 记录事件 | IP 记录 |
|---------|---------|---------|
| 用户操作 | register, login, logout, send_message, rate, confirm | ✅ |
| 工程师操作 | login, logout, reply, assign, resolve, close, transfer, escalate, submit_knowledge | ✅ |
| 管理员操作 | 所有 CURD + 配置修改 + 状态干预 + 关闭 | ✅ |
| 系统操作 | auto_close, auto_rate, archive | system 标识 |
| 登录失败 | login_failure (含失败原因) | ✅ |

### 7.3 安全防护清单

| 防护措施 | 优先级 | 实现方式 |
|---------|--------|---------|
| bcrypt 密码哈希 | P1 | 替换当前 SHA256 |
| CSRF Token | P1 | Flask-WTF 或自定义 token |
| HTTPS 强制跳转 | P1 | Nginx 301 redirect |
| 会话超时 | P2 | Flask session 有效期 24h |
| API 限流 | P2 | Flask-Limiter，/api/chat 限 30 次/分 |
| API Key 加密 | P2 | system_config 敏感字段 AES 加密 |
| 登录失败锁定 | P3 | 5 次失败/15 分钟，redis 或内存缓存 |
| 日志防篡改 | P3 | audit_log 仅 insert，无 update/delete API |

---

## 八、硬件资源需求

### 8.1 最小部署配置（1 台服务器，含 LLM）

| 组件 | 规格 | 说明 |
|------|------|------|
| CPU | 8 核 (x86_64) | Intel Xeon / AMD EPYC |
| 内存 | **32 GB** | LLM 推理 + Flask + SQLite 共享 |
| 磁盘 | **200 GB SSD** | 数据 + 图片 + 知识库 + 备份 |
| GPU | **可选**（推荐 24 GB 显存） | 运行本地 LLM（如无 GPU，用 CPU 小模型） |
| 网络 | 千兆以太网 | 内网互连 |
| OS | Ubuntu 22.04 LTS / CentOS 7+ | — |

### 8.2 分离部署配置（推荐）

#### 应用服务器（SmartCS）

| 组件 | 规格 |
|------|------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 磁盘 | 200 GB SSD |
| 网络 | 千兆 |

#### LLM 推理服务器（可选）

| 组件 | 规格 |
|------|------|
| CPU | 8 核 |
| 内存 | 32 GB |
| GPU | NVIDIA RTX 4090 24GB / A10 / A100 |
| 磁盘 | 100 GB SSD |
| 软件 | Ollama / vLLM + Qwen2.5 14B 或更小模型 |

#### Whisper STT 服务器（可复用应用服务器）

| 组件 | 规格 |
|------|------|
| CPU | 4 核（支持 AVX2） |
| 内存 | 8 GB |
| GPU | CPU 可跑（faster-whisper 小模型） |

### 8.3 存储估算

| 数据类型 | 年增长 | 10 年累计 |
|---------|--------|---------|
| 数据库（SQLite） | ~1.6 GB | ~16 GB |
| 用户上传图片 | ~60-100 MB/月 → ~1 GB/年 | ~10 GB |
| 用户语音文件 | ~100-200 MB/月 → ~2 GB/年 | ~20 GB |
| 知识库文档 | ~200 MB/年 | ~2 GB |
| 备份（3 份循环） | 3x 数据库 ≈ 5 GB | 5 GB 常量 |
| **合计** | **~5 GB/年** | **~50 GB** |

**建议初始磁盘：200 GB（5 倍安全余量）**

### 8.4 网络要求

| 方向 | 协议 | 端口 | 说明 |
|------|------|------|------|
| 用户→Nginx | HTTPS | 443 | 浏览器访问 |
| Nginx→Flask | HTTP | 8080 | 内网反向代理 |
| SmartCS→LLM | HTTP | 11434 或 8000 | Ollama/vLLM API |
| SmartCS→Whisper | HTTP | 9090 | STT 服务 |
| SmartCS→LDAP | LDAP | 389 或 636 | 认证（可选） |
| SmartCS→SMTP | SMTP | 25 或 587 | 邮件通知（可选） |

---

## 九、软件资源需求

### 9.1 基础软件

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.8+ | 后端运行时 |
| Nginx | 1.18+ | 反向代理 + HTTPS |
| SQLite | 3.x（系统自带） | 数据库（WAL 模式） |
| systemd | 系统自带 | 进程管理 |
| OpenSSL | 1.1+ | 自签证书生成 |

### 9.2 Python 依赖

| 包 | 用途 |
|----|------|
| Flask==2.x | Web 框架 |
| gunicorn==21.x | WSGI 服务器（生产） |
| bcrypt==4.x | 密码哈希（P1 改造） |
| python-dotenv | 环境变量 |
| (可选) faster-whisper | 本地 STT |
| (可选) openai | LLM API 客户端（兼容本地端点） |

### 9.3 可选依赖（按需部署）

| 软件 | 用途 | 部署方式 |
|------|------|---------|
| Ollama | 本地 LLM 推理 | Docker 或直接安装 |
| vLLM | 高性能 LLM 推理 | Docker + CUDA |
| faster-whisper | 本地语音识别 | pip install |
| OpenLDAP | 认证服务 | Docker |
| GitLab (内网) | 代码仓库镜像 | Docker 部署 |

---

## 十、部署架构

### 10.1 一键部署流程

```bash
# 1. 服务器初始化
apt update && apt install -y nginx python3 python3-pip openssl

# 2. 生成自签证书
scripts/gen_cert.sh  # 输出到 /etc/nginx/certs/smartcs.*

# 3. 配置 Nginx
cp config/nginx/smartcs.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/smartcs.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 4. 安装 Python 依赖
pip3 install -r requirements.txt

# 5. 初始化数据库
python3 scripts/init_db.py  # 创建表 + 迁移旧数据

# 6. 配置 systemd 服务
cp config/systemd/smartcs.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable smartcs && systemctl start smartcs

# 7. 验证
curl -k https://localhost/api/stats
```

### 10.2 目录结构（生产部署）

```
/home/deploy/smart-cs/
├── app.py               # 入口
├── config.py
├── models.py
├── state_machine.py
├── routes/              # API 路由
├── services/            # 业务服务
├── adapters/            # 适配器
├── templates/           # Jinja2 模板
├── static/              # 静态资源
├── data/
│   └── smartcs.db       # SQLite 数据库（WAL）
├── uploads/
│   ├── images/          # 用户图片
│   └── audio/           # 语音文件
├── knowledge/           # 知识库源文件
├── scripts/             # 运维脚本
├── tests/               # 测试
├── docs/                # 文档
├── logs/                # 应用日志
│   ├── access.log
│   └── error.log
└── requirements.txt
```

### 10.3 systemd 服务配置

```ini
[Unit]
Description=SmartCS Service
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/smart-cs
ExecStart=/usr/local/bin/gunicorn -w 4 -b 127.0.0.1:8080 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 10.4 Nginx 配置要点

```nginx
server {
    listen 443 ssl;
    server_name smartcs.internal;
    
    ssl_certificate /etc/nginx/certs/smartcs.pem;
    ssl_certificate_key /etc/nginx/certs/smartcs.key;
    
    # HTTPS 强加密套件
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        
        # 上传文件大小限制
        client_max_body_size 50M;
        
        # 长轮询超时
        proxy_read_timeout 30s;
    }
}

server {
    listen 80;
    server_name smartcs.internal;
    return 301 https://$host$request_uri;  # HTTP → HTTPS 强制跳转
}
```

### 10.5 备份策略

```bash
# 每日凌晨 2:00 执行（crontab）
0 2 * * * /home/deploy/smart-cs/scripts/backup.sh

# backup.sh 内容：
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/backup/smartcs"
mkdir -p $BACKUP_DIR

# 1. SQLite 在线备份（WAL 模式安全）
sqlite3 /home/deploy/smart-cs/data/smartcs.db \
  ".backup $BACKUP_DIR/smartcs_$DATE.db"

# 2. 上传文件增量备份
rsync -a /home/deploy/smart-cs/uploads/ $BACKUP_DIR/uploads/

# 3. 保留最近 30 天备份，旧备份清理
find $BACKUP_DIR -name "smartcs_*.db" -mtime +30 -delete
```

---

## 十一、开发实施路线图

### 11.1 实施阶段

```
Phase 0 — 架构重构（2-3 天）
  ├── 代码拆分：app.py → routes/ + services/ + adapters/
  ├── 数据库迁移：旧状态→新状态 + 游客清理
  ├── system_config 新增配置项前端
  └── Gunicorn 部署 + 自签证书

Phase 1 — 状态机改造（3 天） ★P0
  ├── 创建时机：首次发消息即创建工单
  ├── 新状态流转（created/processing/resolved/rated/closed）
  ├── 超时调度（auto_close_min / auto_rate_hours）
  ├── 移除 L1 直接关 / L2 请求关  → 统一关闭流程
  ├── 工程师端工单列表适配新状态
  └── 用户端移除游客场景

Phase 2 — 工程师端增强（2 天） ★P1
  ├── L1~L4 级别扩展 + 名称可配
  ├── 四标签工单管理（待处理/已处理/全部经手/搜索）
  ├── 身份切换（工程师→用户报修模式）
  └── 知识沉淀（提交→审核→发布）

Phase 3 — 管理后台重构（2 天） ★P1
  ├── 三大模块重组（配置/业务/审计）
  ├── 数据分析仪表盘（单位/系统/拦截率）
  ├── 审计增强（IP 记录 + 登录日志）
  └── 整体色调配置

Phase 4 — 扩展功能（2-3 天） ★P2
  ├── 语音消息（前端录音 + Whisper STT）
  ├── 问题升级功能
  ├── 安全的 HTTPS 证书管理
  └── bcrypt + CSRF 防护

Phase 5 — 远期功能 ★P3
  ├── 用户端 SSO
  ├── 工程师绩效统计
  ├── 人员同步
  └── 原生 SDK
```

### 11.2 依赖关系

```
Phase 0 ──── Phase 1 ──── Phase 2 ──── Phase 4
  │                         │
  │                         └── Phase 3
  │
  └── Phase 5（可并行）
```

Phase 1（状态机）是核心阻塞项，所有其他阶段依赖它。

### 11.3 团队建议

| 规模 | 建议 | 预估工期 |
|------|------|---------|
| 1 人全栈 | 按 Phase 顺序串行执行 | **6-8 周** |
| 2 人（后端+前端） | Phase 0+1 后端主攻；Phase 2+3 前后端并行 | **3-4 周** |
| 3 人（后端×2 + 前端） | Phase 0 后，Phase 1/2/4 后端并行，前端统一 | **2-3 周** |

---

## 十二、测试策略

### 12.1 测试层级

| 层级 | 覆盖 | 工具 | 目标 |
|------|------|------|------|
| 单元测试 | 状态机、适配器、工具函数 | unittest/pytest | 覆盖率 > 70% |
| 集成测试 | API 端点（全链路） | pytest + requests | 62 项→**100+ 项** |
| 端到端测试 | 用户→AI→工程师→关闭 完整流程 | 脚本自动化 | 无人工干预 |
| 性能测试 | 轮询/搜索/并发 | locust / wrk | 1000 单/天基准验证 |

### 12.2 核心测试场景

| 场景 | 状态机路径 | 优先级 |
|------|-----------|--------|
| 用户注册→发消息→AI 回复 | created | P0 |
| 用户发消息→转人工→工程师受理→完成 | created→processing | P0 |
| 工程师提请完成→用户评价 | processing→resolved→rated | P0 |
| 用户不评价→24h 超时自动评价 | resolved→rated（超时） | P0 |
| 工程师关闭→只读 | rated→closed | P0 |
| 已创建→20min 超时→自动关闭 | created→closed（超时） | P0 |
| 管理员强制关闭任意状态 | any→closed | P1 |
| 知识提交→审核→通过→AI 可搜 | pending→approved | P1 |
| 工程师身份切换→用户报修→切回 | — | P1 |
| 80 人并发轮询 | — | P2 |
| 语音上传→STT→文字→AI | — | P2 |

---

## 附录

### A. 关键设计决策（RAD）

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 数据库 | SQLite / PG / MySQL | **SQLite WAL** | 1,000 单/天舒适区；避免中间件复杂度 |
| 实时推送 | WebSocket / 轮询 | **轮询** | 80 人 × 3s 轮询 17req/s，足够且简单 |
| AI 集成 | 硬编码 / 配置化 | **配置化** | 支持内网 LLM 切换 Zero 代码改动 |
| 前端框架 | Vue/React / Jinja2 | **Jinja2** | 1,000 单/天不需要 SPA；减少部署复杂度 |
| 认证 | 本地 / LDAP / OIDC | **适配器模式** | 支持多种认证源切换 |
| 审计存储 | SQLite / 独立日志 | **SQLite + 归档** | 审计日志量小（~500 条/天），SQLite 足够 |

### B. 预留扩展点

| 扩展点 | 设计方式 | 何时启用 |
|--------|---------|---------|
| PostgreSQL | 适配器模式，DB_ENGINE 环境变量 | >5,000 单/天 |
| WebSocket | 替换 3s 轮询，消息引擎层抽象 | >300 工程师 |
| 对象存储 | 文件上传层抽象（本地/OSS/MinIO） | 磁盘 >80% |
| Redis 缓存 | 缓存热点工单/配置 | API 响应 >500ms |
| 邮件/短信通知 | 适配器模式，添加 SMTP/短信适配器 | 需要时 |

---

**版本：** v1.0  
**关联需求文档：** `docs/SmartCS-需求文档.md` v5.6  
**最后更新：** 2026-05-20  
**设计人：** 旺财
