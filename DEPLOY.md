# SmartCS 部署手册

> 适用于 Python 3.8+ / Flask / SQLite / Nginx 环境

---

## 目录

1. [环境要求](#环境要求)
2. [快速部署](#快速部署)
3. [Nginx 配置](#nginx-配置)
4. [生产环境优化](#生产环境优化)
5. [升级更新](#升级更新)
6. [备份与恢复](#备份与恢复)
7. [常见问题](#常见问题)

---

## 环境要求

| 组件 | 最低版本 | 推荐 |
|------|---------|------|
| Python | 3.8 | 3.8+ |
| pip | 21.x | 最新 |
| Nginx | 1.18 | 1.24+ |
| 内存 | 512 MB | 1 GB+ |
| 磁盘 | 200 MB | 1 GB+ |
| 操作系统 | Linux | Ubuntu 20.04+ / CentOS 7+ |

> SQLite 内置，无需额外安装数据库。

---

## 快速部署

### 1️⃣ 安装 Python 依赖

```bash
# 创建虚拟环境 (推荐)
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2️⃣ 配置环境变量

```bash
# 编辑 ~/.bashrc 或直接 export
export DASHSCOPE_API_KEY="your-dashscope-key"    # 通义千问 AI
export API_BASE_URL="https://api.deepseek.com/v1" # 或自定义 AI 地址
export MODEL_NAME="deepseek-chat"                 # 模型名称
export SECRET_KEY="your-strong-secret-key"        # 会话密钥
```

> 不配置 AI API 时，系统仍可运行（自动回复使用基础回答）。

### 3️⃣ 启动服务

```bash
cd smartcs/

# 创建数据目录
mkdir -p data uploads

# 开发模式 (直接前台运行)
python app.py

# 生产模式 (后台运行)
nohup python app.py > app.log 2>&1 &

# 查看日志
tail -f app.log
```

### 4️⃣ 验证部署

```bash
# 检查页面
curl -s http://localhost:5000/ | head -5
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/

# 运行集成测试
python test_smartcs.py
```

---

## Nginx 配置

将以下配置保存到 `/etc/nginx/conf.d/smartcs.conf`：

```nginx
server {
    listen 8080;
    server_name your-domain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }

    location /api/upload {
        proxy_pass http://127.0.0.1:5000;
        client_max_body_size 50M;
        proxy_read_timeout 120s;
    }
}
```

```bash
# 重载 Nginx
sudo nginx -t && sudo systemctl reload nginx
```

> **安全提示：** 建议配置 HTTPS（使用 Let's Encrypt 免费证书）。

---

## 生产环境优化

### Systemd 服务 (推荐)

创建 `/etc/systemd/system/smartcs.service`：

```ini
[Unit]
Description=SmartCS Customer Service System
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/smart-cs
Environment=PATH=/home/deploy/smart-cs/venv/bin:/usr/bin
Environment=DASHSCOPE_API_KEY=your-key
Environment=SECRET_KEY=your-secret
ExecStart=/home/deploy/smart-cs/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smartcs
```

### 数据库优化

```sql
-- 手动执行 VACUUM 压缩数据库
sqlite3 data/smartcs.db "VACUUM;"

-- 定期备份
cp data/smartcs.db "data/smartcs_$(date +%Y%m%d).db"
```

### 安全配置

1. **修改默认密码** — 所有客服/管理员账户
2. **配置 HTTPS** — 使用 Certbot 获取免费证书
3. **限制外网访问** — 仅通过 Nginx 暴露 8080 端口
4. **日志轮转** — 配置 logrotate 管理日志文件

---

## 升级更新

```bash
# 1. 备份当前版本
cp app.py app.py.bak.$(date +%Y%m%d)
cp data/smartcs.db data/smartcs.db.$(date +%Y%m%d)

# 2. 更新代码
git pull origin main

# 3. 重启服务
fuser -k 5000/tcp
nohup python app.py > app.log 2>&1 &

# 4. 验证
python test_smartcs.py
```

---

## 备份与恢复

### 备份

```bash
#!/bin/bash
# backup.sh - 每日备份脚本
BACKUP_DIR="/backups/smartcs"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份数据库
cp /home/deploy/smart-cs/data/smartcs.db $BACKUP_DIR/smartcs_$DATE.db

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /home/deploy/smart-cs/uploads/

# 备份知识库
tar -czf $BACKUP_DIR/knowledge_$DATE.tar.gz /home/deploy/smart-cs/knowledge/

# 保留最近 30 天
find $BACKUP_DIR -name "*.db" -type f -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -type f -mtime +30 -delete
```

### 恢复

```bash
# 停止服务
fuser -k 5000/tcp

# 恢复数据库
cp /backups/smartcs/smartcs_20260401.db /home/deploy/smart-cs/data/smartcs.db

# 恢复上传文件
tar -xzf /backups/smartcs/uploads_20260401.tar.gz -C /home/deploy/smart-cs/

# 重启服务
nohup python app.py > app.log 2>&1 &
```

---

## 常见问题

### `Port 5000 is in use`

```bash
# 查找占用进程
fuser 5000/tcp
# 或
lsof -i :5000

# 杀掉进程
fuser -k 5000/tcp
```

### 数据库损坏

```bash
# 尝试修复
sqlite3 data/smartcs.db ".recover" | sqlite3 data/smartcs_recovered.db
mv data/smartcs_recovered.db data/smartcs.db
```

### AI 不回复

- 检查 `DASHSCOPE_API_KEY` 是否配置
- 检查 API 地址是否可访问
- 查看 `app.log` 中是否有 API 错误信息

### 图片上传失败

- 检查 `uploads/images/` 目录是否存在
- 检查 Nginx 的 `client_max_body_size` 配置
- 检查磁盘空间

---

> 📖 使用说明请参考 [USAGE.md](USAGE.md)
