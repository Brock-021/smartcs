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

### 状态机驱动

工单有明确的状态流转，由 `ticket_machine` 管理：

```
open → assigned → confirmed → resolved → closed
  ↓        ↑           ↓
  └──→ escalated ──────┘
```

- 每个状态变更自动记录审计日志
- 状态变更触发 Webhook 通知

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
