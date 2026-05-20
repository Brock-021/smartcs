# SmartCS 架构说明

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML5 + CSS3 + JavaScript | 原生，无框架依赖 |
| 后端 | Flask 3.0 (Python 3.8+) | 全栈 Web 框架 |
| 数据库 | SQLite 3 (WAL 模式) | 零配置，嵌入式数据库 |
| 反向代理 | Nginx | 静态资源、SSL、负载 |
| AI 引擎 | DeepSeek / 通义千问 | REST API 调用 |

## 核心设计

### 状态机驱动（新状态机 v4.1）

工单有明确的状态流转，由 `ticket_machine` 管理：

```
created → processing → resolved → rated → closed
  │                       │
  ├── timeout ────────────┤
  │  (auto_close_min)     │ (auto_rate_hours)
  ▼                       ▼
closed ──────────────── rated
```

**状态定义：**

| 状态 | 含义 | 触发条件 | 所有者 |
|------|------|---------|--------|
| `created` | 已创建，AI 自助阶段 | 用户首次发消息 | 用户/管理员 |
| `processing` | 处理中，客服已受理 | 转人工或客服接单 | 指定客服 |
| `resolved` | 已处理，待用户确认评价 | 客服提请完成 | 用户 |
| `rated` | 已评价，待客服关闭 | 用户评价或超时自动 | 客服/管理员 |
| `closed` | 已关闭，只读 | 客服或管理员关闭 | 只读 |

**流转规则：**
- 用户首次发消息即创建工单（`created`）
- 用户转人工 → `created → processing`
- 客服受理 → 工单分配给自己
- 客服提请完成 → `processing → resolved`
- 用户确认评价 → `resolved → rated`
- `resolved` 超时自动进 `rated`（`auto_rate_hours`，默认24h）
- 客服关闭工单 → `rated → closed`
- `created` 超时自动关闭 → `created → closed`（`auto_close_min`，默认20min）
- 管理员可强制关闭任意状态工单

- 每个状态变更自动记录审计日志
- 状态变更触发 Webhook 通知

### 配置系统架构（v4.1 新增）

#### system_config 表结构

所有系统配置以 key-value 形式存储在 `system_config` 表中：

```sql
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,          -- 配置键名
    value TEXT NOT NULL,           -- 配置值（字符串存储）
    updated_at TEXT                -- 最后更新时间
);
```

**配置分类：**

| 分类 | 管理界面 | 管理员角色 | 示例键 |
|------|---------|-----------|--------|
| 系统配置 | ⚙️ 系统配置 | 系统管理员 | `api_key`, `api_base_url`, `model_name`, `auto_close_min` |
| 安全配置 | 🔒 安全配置 | 安全管理员 | `password_min_length`, `login_max_attempts`, `audit_log_retention_days` |
| 品牌配置 | 🎨 品牌配置 | 系统管理员 | `brand_name`, `brand_primary_color`, `brand_logo_path` |
| 系统行为 | 自动读取 | — | `session_lifetime`, `pagination_per_page`, `max_upload_size_mb` |

#### 配置加载机制

配置使用两级缓存加载：

```
API请求 → context_processor → get_brand_config()
                                   │
                                   ▼
                           get_system_config()
                                   │
                           ┌───────┴───────┐
                           │               │
                      _config_cache   直接查数据库
                      (5分钟过期)         (首次/缓存过期)
                           │
                           ▼
                     返回配置字典
```

- `get_system_config()`：全局函数，使用模块级 `_config_cache` 字典缓存，5分钟过期
- `get_brand_config()`：封装品牌配置，从 `get_system_config()` 取值并提供默认值
- `@app.context_processor`：将品牌配置注入所有 Jinja2 模板，模板中可直接使用 `{{ brand_name }}`
- `invalidate_config_cache()`：配置修改后调用，清空缓存使下次读取走数据库
- `@app.before_request` 中调用 `_sync_app_config_from_db()`：每次请求前同步 Flask 配置

#### CSS 变量注入方案

所有模板中的硬编码颜色（原 `#1a73e8`）已替换为 CSS 变量：

```css
:root {
    --primary-color: var(--brand-primary-color, #1a73e8);
}

/* 使用示例 */
.button {
    background: var(--primary-color);
}
```

CSS 变量通过模板引擎注入：

```html
<style>
:root {
    --brand-primary-color: '{{ brand_primary_color }}';
}
</style>
```

**生效范围：** 所有 6 个模板（chat.html、admin.html、agent_dashboard.html、agent_login.html、upload.html、user_login.html）

#### PWA 动态化

- `/manifest.json`：从 `get_brand_config()` 读取品牌名称和主题色
- `/sw.js`：从 `get_brand_config()` 读取品牌简称用于缓存命名
- 修改品牌配置后，清除浏览器缓存重新添加到桌面即可看到变化

### AI + 人工混合模式

```
用户消息 → AI 意图识别
    ├── 匹配知识库 → AI 自动回复
    └── 需要人工 → 创建工单 → 推送给客服
```

### 适配器模式

外部系统集成使用适配器模式：

```
IMAdapter (抽象基类)
  ├── WeComAdapter (企业微信)
  ├── DingTalkAdapter (钉钉)
  └── (可扩展其他平台)

ExternalAdapter (外部系统)
  ├── defect (Jira / 禅道)
  └── webhook (HTTP 回调)

AuthProvider (认证)
  ├── OIDCProvider
  └── LDAPProvider
```

## 数据流

```
用户 ──HTTP──→ Nginx (:8080) ──proxy──→ Flask (:5000) ──→ SQLite
                                                │
                                                ├──→ AI API (DeepSeek)
                                                ├──→ IM 推送 (企微/钉钉)
                                                └──→ Webhook (外部系统)
```
