# SmartCS 智能客服系统 v4.1

> 基于 Python Flask 的全功能智能客服工单管理系统，支持 AI 自动应答、人工客服、工单流转、多平台集成、品牌自定义、安全策略配置。

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![Version](https://img.shields.io/badge/Version-4.1-brightgreen)

---

## ✨ 功能特性

### 💬 智能客服
- **AI 自动应答** — 基于知识库的智能问答，自动回复常见问题
- **智能转人工** — 自动识别用户意图，需要时无缝转接人工客服
- **多轮对话** — 保持上下文，支持多轮连续对话

### 🎫 工单管理
- **完整工单生命周期**：待处理 → 受理中 → 待确认 → 已解决 → 已关闭
- **自动关闭** — 解决后用户未响应自动关闭
- **评分评价** — 用户可对服务进行星级评分和反馈
- **工单升级** — 客服可发起升级流程

### 👥 多角色权限
- **普通用户** — 咨询、报修、查工单
- **人工客服** — 处理工单、回复客户、提交缺陷
- **管理员** — 系统配置、用户管理、审计、数据统计

### 🔗 集成能力
- **企业微信** — 消息推送与回调
- **钉钉** — 消息推送
- **LDAP** — 企业目录认证
- **OIDC** — 单点登录 (Keycloak 等)
- **Jira/禅道** — 缺陷自动提交
- **Webhook** — 工单状态变更通知

### 🎨 品牌自定义
- **品牌名称** — 系统名称、简称后台可配置
- **主题色** — 全站主色调 CSS 变量化，一处修改全局生效
- **Logo 配置** — Logo 图片路径、Favicon 路径可配
- **PWA 动态化** — manifest.json、Service Worker 从数据库读取品牌配置

### 🔒 安全策略
- **密码策略** — 最小长度、大小写要求、过期天数可配
- **登录限制** — 失败次数、锁定时间可配
- **审计保留** — 审计日志保留天数可配
- **会话管理** — 会话生命周期、空闲超时全部配置化

### 📱 移动端支持
- **PWA 支持** — 可添加到桌面，支持离线缓存
- **响应式设计** — 手机/平板/桌面自适应
- **底部导航** — 移动端专属 Tab 导航
- **下拉刷新** — 移动端下拉刷新聊天记录

### 📊 运营管理
- **数据统计看板** — 工单趋势、客服绩效、满意度
- **知识库管理** — 上传/编辑/删除知识文档
- **审计日志** — 全量操作记录与追溯
- **CSV 导出** — 工单数据一键导出

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────┐
│                   Nginx (:8080)                  │
│          反向代理 / 静态资源 / SSL               │
└────────────────────┬────────────────────────────┘
                     │ proxy_pass :5000
┌────────────────────▼────────────────────────────┐
│              Flask 应用 (app.py)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ 用户端   │ │ 客服工作台│ │  管理后台        │ │
│  │ /chat    │ │ /agent   │ │  /admin          │ │
│  ├──────────┤ ├──────────┤ ├──────────────────┤ │
│  │ AI问答   │ │ 工单处理 │ │  系统配置        │ │
│  │ 转人工   │ │ 客户沟通 │ │  用户管理        │ │
│  │ 查工单   │ │ 缺陷提交 │ │  审计日志        │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              SQLite 数据库                        │
│  service_tickets / conversations / agents /      │
│  audit_log / im_adapters / external_adapters ... │
└─────────────────────────────────────────────────┘
```

---

## 🗂️ 项目结构

```
smartcs/
├── app.py                  # 主应用 (Flask)
├── test_smartcs.py         # 集成测试
├── requirements.txt        # Python 依赖
├── README.md               # 项目文档 (本文件)
├── DEPLOY.md               # 部署手册
├── USAGE.md                # 使用说明
├── CHANGELOG.md            # 版本历史
├── architecture.md         # 架构详解
│
├── static/
│   └── icon-192.svg        # PWA 图标
│
├── templates/
│   ├── chat.html           # 用户聊天界面 (首页)
│   ├── admin.html          # 管理员后台
│   ├── agent_dashboard.html # 客服工作台
│   ├── agent_login.html    # 客服登录页
│   └── upload.html         # 知识库管理页
│
├── knowledge/
│   └── 事件管理规定.md       # 示例知识库文档
│
└── data/                   # 运行时数据目录
    └── smartcs.db          # SQLite 数据库 (自动创建)
```

---

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python app.py

# 3. 访问 http://localhost:5000
```

> 详细部署步骤请参见 [DEPLOY.md](DEPLOY.md)

---

## 🔑 默认账户

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | `admin@smartcs.com` | `admin123` |
| 客服 | `agent@smartcs.com` | `admin123` |

> ⚠️ 生产环境请立即修改密码

---

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key (AI 问答) | 空 (使用 DeepSeek) |
| `API_BASE_URL` | AI 模型 API 地址 | `https://api.deepseek.com/v1` |
| `MODEL_NAME` | 模型名称 | `deepseek-chat` |
| `ADMIN_PASSWORD` | 管理员公共密码 | `admin123` |
| `SECRET_KEY` | Flask Session 密钥 | `smart-cs-secret-2026` |

---

## 📄 许可证

MIT License — 详情见 LICENSE 文件
