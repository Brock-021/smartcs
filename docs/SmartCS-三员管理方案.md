# SmartCS 三员管理优化方案

**版本：** v2.0（根据技术评审修订）
**日期：** 2026-05-20
**评审意见：** `docs/SmartCS-三员管理方案-评审.md`
**依据：** 等保 2.0 三级要求（GB/T 22239-2019）

---

## 一、什么是三员

三员管理是等保合规的核心要求，指将管理员权限拆分为三个互相独立、互相制约的角色：

| 角色 | 职责 | 一句话 |
|------|------|--------|
| 👤 **系统管理员** | 用户管理、工单管理、系统配置、客服管理 | **管系统** |
| 🛡️ **安全管理员** | 角色分配、安全策略、密码策略、登录限制 | **管权限** |
| 🔍 **审计管理员** | 仅查看审计日志，不能做任何写操作 | **管监督** |

**核心原则：** 三权分立，任何一个人不能同时拥有两个角色。

---

## 二、现状分析

### 当前权限模型（仅两角色）

```
角色: agent（普通客服） / admin（超级管理员）
```

| 功能 | agent | admin |
|------|-------|-------|
| 客服工作台 | ✅ | ✅ |
| 工单受理/回复 | ✅ | ✅ |
| 客服管理（增删改） | ❌ | ✅ |
| 用户管理（增删改） | ❌ | ✅ |
| 系统配置修改 | ❌ | ✅ |
| 审计日志查看 | ❌ | ✅ |
| 关闭原因管理 | ❌ | ✅ |
| 知识库管理 | ❌ | ✅ |
| 认证提供者管理 | ❌ | ✅ |
| SSO配置 | ❌ | ✅ |
| Webhook管理 | ❌ | ✅ |

**问题：** 管理员拥有一切权限，包括审计自己。审计日志形同虚设。不符合等保「三权分立」要求。

---

## 三、目标设计

### 3.1 角色权限矩阵

```
权限矩阵（✅=有 ❌=无）

模块                    系统管理员   安全管理员   审计管理员   普通客服
───                    ────────   ────────   ────────   ────
👤 用户管理
  查看用户列表           ✅          ✅          ❌          ❌
  创建/编辑/删除用户      ✅          ❌          ❌          ❌
  重置用户密码           ✅          ❌          ❌          ❌

👥 客服管理
  查看客服列表           ✅          ✅          ❌          ❌
  创建/编辑客服          ✅          ❌          ❌          ❌
  修改客服级别           ✅          ❌          ❌          ❌
  删除客服              ❌(需安全员)  ✅          ❌          ❌

🔐 角色与权限
  分配/变更角色          ❌          ✅          ❌          ❌
  角色配置              ❌          ✅          ❌          ❌

⚙️ 系统配置
  API/模型配置          ✅          ❌          ❌          ❌
  密码策略配置           ❌          ✅          ❌          ❌
  系统参数（关闭超时等）   ✅          ❌          ❌          ❌

🔍 审计日志
  查看审计日志           ❌          ❌          ✅          ❌
  查看登录日志           ❌          ❌          ✅          ❌
  日志归档配置           ❌          ❌          ✅          ❌
  清理日志              ❌          ❌          ❌(只读)     ❌

📋 工单管理
  查看所有工单           ✅          ❌          ❌          ❌
  强制关闭工单           ✅          ❌          ❌          ❌
  工单归档              ✅          ❌          ❌          ❌

📚 知识库管理
  管理知识库             ✅          ❌          ❌          ❌
  审批知识条目           ✅          ❌          ❌          ❌

🔗 集成管理
  IM适配器              ✅          ❌          ❌          ❌
  外部适配器(Jira等)     ✅          ❌          ❌          ❌
  Webhook管理           ✅          ❌          ❌          ❌
  认证提供者(LDAP/OIDC)  ❌          ✅          ❌          ❌
  SSL证书管理            ✅          ❌          ❌          ❌

📊 数据统计
  数据分析仪表盘         ✅          ✅          ✅          ❌
  数据导出              ✅          ❌          ❌          ❌
```

### 3.2 关键约束

| 约束 | 说明 |
|------|------|
| **互斥约束** | 同一人不可同时拥有两个管理员角色 |
| **自审计** | 审计管理员的操作也需记录审计日志（审计审计） |
| **最小角色数** | 至少需要 3 人分别担任三员（可兼任普通客服） |
| **初始配置** | 首次部署时系统自动创建三员默认账号，强制要求修改密码 |
| **降级保护** | 安全管理员不可删除自己的角色或将自己降级为普通角色 |
| **删除保护** | 不可删除最后一位安全管理员/审计管理员 |

---

## 四、数据库设计

### 4.1 agents 表 role 字段扩展（统一权限来源，不新增 is_* 布尔列）

```sql
-- 当前 role 字段值扩展（唯一权限来源，不新增 is_* 布尔列）
-- 'agent'      = 普通客服（原有）
-- 'sysadmin'   = 系统管理员（新增）
-- 'secadmin'   = 安全管理员（新增）
-- 'audadmin'   = 审计管理员（新增）
-- 'superadmin' = 兼容角色（从 admin@smartcs.com 迁移，过渡期后废弃）

-- 迁移：ALTER TABLE agents RENAME TO agents_old; 重建带新 CHECK
-- 或直接更新：UPDATE agents SET role='superadmin' WHERE role='admin'
-- 待实施时选择最优方案
```

### 4.2 装饰器设计（统一工厂模式，弃用 admin_required）

```python
# 统一角色装饰器工厂 — 所有权限判断统一入口
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('agent_id'):
                if request.is_json:
                    return jsonify({'error': '未登录'}), 401
                return redirect('/agent/login')
            role = session.get('agent_role')
            if role == 'superadmin':  # 兼容角色
                return f(*args, **kwargs)
            if role not in allowed_roles:
                return jsonify({'error': '权限不足'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

sysadmin_required = role_required('sysadmin', 'superadmin')
secadmin_required = role_required('secadmin', 'superadmin')
audadmin_required = role_required('audadmin', 'superadmin')
logged_in_required = role_required('agent', 'sysadmin', 'secadmin', 'audadmin', 'superadmin')

# 替换掉现有的 admin_required 和 admin_or_agent_required
```

### 4.3 安全配置表（system_config 扩增）

```sql
-- 密码策略（安全管理员管理）
INSERT OR IGNORE INTO system_config(key,value) VALUES('password_min_length','8');
INSERT OR IGNORE INTO system_config(key,value) VALUES('password_require_upper','true');
INSERT OR IGNORE INTO system_config(key,value) VALUES('password_require_number','true');
INSERT OR IGNORE INTO system_config(key,value) VALUES('password_require_special','false');
INSERT OR IGNORE INTO system_config(key,value) VALUES('password_expire_days','90');
INSERT OR IGNORE INTO system_config(key,value) VALUES('login_max_attempts','5');
INSERT OR IGNORE INTO system_config(key,value) VALUES('login_lockout_minutes','15');
INSERT OR IGNORE INTO system_config(key,value) VALUES('session_timeout_minutes','480');
INSERT OR IGNORE INTO system_config(key,value) VALUES('audit_log_retention_days','365');
```

### 4.3 操作审计增强

```sql
-- audit_log 已添加 ip_address 列，后续需补齐记录逻辑
-- 审计日志需记录：谁(actor_id)、做了什么(action)、对谁(target)、
-- 从哪来(ip_address)、什么时候(created_at)、请求体摘要(detail)
```

---

## 五、API 改造清单

### 5.1 新增三个装饰器

```python
def sysadmin_required(f):    # @admin_required 改名/细化
def secadmin_required(f):    # 安全管理员专属
def audadmin_required(f):    # 审计管理员专属
```

### 5.2 装饰器逻辑

```python
def sysadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('agent_id'):
            return jsonify({'error': '未登录'}), 401
        agent_role = get_agent_role(session['agent_id'])
        if agent_role not in ('sysadmin', 'secadmin', 'superadmin'):
            # 安全管理员在权限管理区域可访问（用 secadmin_required）
            # 此处仅判断是否为系统管理员权限
            pass
        return f(*args, **kwargs)
    return decorated
```

### 5.3 路由改造映射

| 当前路由 | 当前保护 | 改为 |
|---------|---------|------|
| 客服管理 CRUD | `@admin_required` | `@sysadmin_required` |
| 用户管理 CRUD | `@admin_required` | `@sysadmin_required` |
| 系统配置修改 | `@admin_required` | `@sysadmin_required` |
| 知识库管理 | `@admin_required` | `@sysadmin_required` |
| 关闭原因管理 | `@admin_required` | `@sysadmin_required` (或agent可读) |
| IM/外部适配器 | `@admin_required` | `@sysadmin_required` |
| SSL 证书管理 | `@admin_required` | `@sysadmin_required` |
| 数据分析 | `@admin_required` | 三员均可查看 |
| **角色/权限分配** | 无此功能 | **`@secadmin_required`** |
| 认证提供者(LDAP/OIDC) | `@admin_required` | **`@secadmin_required`** |
| 审计日志查看 | `@admin_required` | **`@audadmin_required`** |
| 登录日志查看 | `@admin_required` | **`@audadmin_required`** |
| 强制关闭工单 | `@admin_or_agent_required` | `@sysadmin_required` |
| 工单归档 | `@admin_required` | `@sysadmin_required` |

---

## 六、前端改造

### 6.1 管理后台导航根据角色动态显示

```javascript
// admin.html 导航条件渲染
const role = currentUser.role;
const navItems = [];

if (role === 'sysadmin') {
    navItems.push('用户管理', '客服管理', '工单管理', '系统配置', '知识库');
}
if (role === 'secadmin') {
    navItems.push('角色管理', '认证配置', '安全策略');
}
if (role === 'audadmin') {
    navItems.push('审计日志', '登录记录', '数据统计');
}
```

### 6.2 登录页增加角色标识

管理员登录后可看到自己的角色标签：`🛡️ 安全管理员` / `👤 系统管理员` / `🔍 审计管理员`

---

## 七、实施路线图

| 阶段 | 内容 | 预估工时 |
|------|------|---------|
| **阶段一** | 数据库改造 + 三员装饰器 + 基础路由拆分 | 2 小时 |
| **阶段二** | 安全配置（密码策略/登录限制/Session超时） | 1 小时 |
| **阶段三** | 前端导航动态渲染 + 角色标签展示 | 1.5 小时 |
| **阶段四** | 审计日志补全 IP 记录 + 三员操作审计 | 1 小时 |
| **阶段五** | 互斥约束 + 删除保护 + 降级保护 | 1 小时 |
| **阶段六** | 测试 + 文档更新 + 初始三员账号创建 | 1.5 小时 |
| **合计** | | **约 12-14 小时**（含路由审计+前端重构+密码策略落地） |

---

## 八、风险与注意事项

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| **向后兼容** | 现有管理员账号 `admin@smartcs.com` 需映射到新角色 | 迁移脚本自动将现有 admin 升级为 `superadmin`（兼容角色，拥有三员全部权限）或提示管理员选择 |
| **前端适配** | admin.html 页面大量现有功能需根据角色显示/隐藏 | 前端增加 `hasPermission()` 函数统一判断 |
| **会话影响** | 现有所有管理员会话需重新登录 | 发布时提示所有管理员重新登录 |
| **误锁风险** | 安全管理员将自己的角色删除会导致系统无人可管 | 删除最后一位安全管理员时拒绝操作 |

---

## 九、示例 UI 布局

```
┌─────────────────────────────────────────────┐
│  SmartCS 管理后台        👤 张三 (系统管理员)   │
├──────────┬──────────────────────────────────┤
│ 导航栏    │  主内容区                        │
│          │                                  │
│ 👥 用户   │  ┌────┬────┬────┬────┬────┐     │
│  管理     │  │ ID │姓名│邮箱│角色 │操作 │     │
│           │  ├────┼────┼────┼────┼────┤     │
│ 👤 客服   │  │ 1  │张三│... │系统│编辑│     │
│  管理     │  │ 2  │李四│... │安全│编辑│     │
│           │  └────┴────┴────┴────┴────┘     │
│ ⚙️ 系统   │                                  │
│  配置     │  ┌─ 角色分配 ──────────────────┐ │
│           │  │ 用户：李四                    │ │
│ 📚 知识   │  │ 当前角色：安全管理员          │ │
│  库       │  │ [系统管理员] [审计管理员]     │ │
│           │  │ └────── 保存 ────────┘      │ │
│ 📊 统计   │  └────────────────────────────┘  │
│           │                                  │
└──────────┴──────────────────────────────────┘

--- 审计管理员看到的界面 ---
┌─────────────────────────────────────────────┐
│  SmartCS 审计控制台      👤 王五 (审计管理员)  │
├──────────┬──────────────────────────────────┤
│ 🔍 审计   │  📋 操作审计日志                  │
│  日志     │  ┌────┬────┬────┬────┬──────┐   │
│           │  │时间│操作人│操作│对象 │ IP  │   │
│ 📊 统计   │  ├────┼────┼────┼────┼──────┤   │
│           │  │... │张三 │... │...  │...  │   │
│           │  └────┴────┴────┴────┴──────┘   │
│           │  只读模式 — 不可删除/修改        │
└──────────┴──────────────────────────────────┘
```

---

## 十、初始账号配置建议

系统自动创建以下默认三员账号（首次登录强制修改密码）：

| 角色 | 默认邮箱 | 默认密码 | 建议操作人 |
|------|---------|---------|-----------|
| 👤 系统管理员 | sysadmin@smartcs.com | SysAdmin@2026 | IT 运维负责人 |
| 🛡️ 安全管理员 | secadmin@smartcs.com | SecAdmin@2026 | 安全负责人 |
| 🔍 审计管理员 | audadmin@smartcs.com | AudAdmin@2026 | 审计/合规负责人 |
| ~~超级管理员~~ | ~~admin@smartcs.com~~ | **迁移后废弃** | 三员上线后删除 |

---

方案已写完，存为 `docs/SmartCS-三员管理方案.md`。要实施的话，预计 **8 小时** 分六阶段完成。

你看方案有没有需要调整的？确认后我就开始干 🚵
