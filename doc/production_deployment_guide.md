# Zchat 生产环境部署与运维指南

本文档提供 Zchat 应用的完整生产环境部署与运维指南，包括系统架构、部署方式、监控配置和维护操作等内容。

## 目录

1. [系统架构](#系统架构)
2. [部署方式](#部署方式)
   - [Docker 部署](#docker-部署)
   - [传统服务器部署](#传统服务器部署)
3. [数据库配置](#数据库配置)
4. [HTTPS 配置](#https-配置)
5. [监控系统](#监控系统)
6. [维护操作](#维护操作)
7. [部署检查清单](#部署检查清单)
8. [故障排除](#故障排除)

## 系统架构

Zchat 使用以下主要组件：

- **应用服务**: Flask 应用，负责核心业务逻辑
- **MySQL**: 存储结构化数据（用户账户、关系等）
- **MongoDB**: 存储非结构化数据（文档、聊天记录等）
- **MeiliSearch**: 提供全文搜索功能
- **Nginx**: 反向代理和静态资源服务
- **Prometheus + Grafana**: 系统监控

系统架构图：
```
            ┌─────────────┐
            │    Nginx    │
            │ (反向代理/SSL) │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │  Flask App  │
            │ (Gunicorn)  │
            └──┬─────┬────┘
               │     │
     ┌─────────┘     └────────┐
     ▼                        ▼
┌─────────┐             ┌──────────┐
│  MySQL  │             │ MongoDB  │
└─────────┘             └──────────┘
     │                        │
     └─────────┬─────────────┘
               │
               ▼
        ┌─────────────┐
        │ MeiliSearch │
        └─────────────┘
               │
               ▼
     ┌───────────────────┐
     │ Prometheus/Grafana│
     │    (监控系统)      │
     └───────────────────┘
```

## 部署方式

Zchat 提供两种部署方式：Docker 部署和传统服务器部署。

### Docker 部署

Docker 部署是推荐的生产环境部署方式，提供更好的隔离性和可移植性。

#### 系统要求

- Docker 20.10+ 和 Docker Compose 2.0+
- 至少 4GB RAM
- 至少 20GB 磁盘空间
- 开放端口：80、443（应用）和 3000（Grafana，可选）

#### 快速部署步骤

1. 获取代码并进入项目目录：

```bash
git clone https://github.com/jsyqrt/chat_server.git
cd chat_server
```

2. 确保脚本有执行权限：

```bash
chmod +x docker-start.sh docker-stop.sh
```

3. 启动服务：

```bash
./docker-start.sh
```

启动脚本会自动：
- 检查并创建必要的配置文件
- 为开发环境生成自签名证书（生产环境请替换为有效证书）
- 创建必要的目录和初始化脚本
- 启动所有容器服务

4. 停止服务：

```bash
./docker-stop.sh
```

#### Docker 配置详解

Docker Compose 配置包含以下主要服务：

- **app**: Zchat Flask 应用，使用 Gunicorn 作为 WSGI 服务器
- **nginx**: 反向代理和 SSL 终结
- **mysql**: 关系型数据库
- **mongodb**: 文档数据库
- **meilisearch**: 搜索服务
- **prometheus**: 指标收集
- **node-exporter**: 系统指标收集
- **grafana**: 指标可视化和告警

可通过修改 `docker-compose.yml` 根据需要调整配置。

### 传统服务器部署

对于不使用 Docker 的环境，可以采用传统的服务器部署方式。

#### 系统要求

- Ubuntu 20.04 LTS 或更高版本
- Python 3.11 或更高版本
- Nginx 1.18 或更高版本
- 4核 CPU、8GB 内存和 50GB 存储（推荐）

#### 部署步骤

1. 准备系统环境：

```bash
# 更新系统并安装基础软件包
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx
```

2. 创建应用用户和目录：

```bash
sudo useradd -m -s /bin/bash zchat
sudo mkdir -p /opt/zchat
sudo chown zchat:zchat /opt/zchat
```

3. 获取代码并准备环境：

```bash
# 切换到应用用户
sudo su - zchat

# 克隆代码
git clone https://github.com/jsyqrt/chat_server.git /opt/zchat
cd /opt/zchat

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

4. 使用提供的脚本启动应用：

```bash
# 确保脚本有执行权限
chmod +x prod_start.sh prod_stop.sh

# 启动应用
./prod_start.sh
```

该脚本将：
- 检查并创建必要的虚拟环境和目录
- 安装依赖
- 启动 MeiliSearch 服务（如有需要）
- 使用 Gunicorn 启动 Flask 应用

5. 停止应用：

```bash
./prod_stop.sh
```

## 数据库配置

### MySQL 配置

MySQL 用于存储结构化数据，包括用户信息、授权和其他关系数据。

#### Docker 环境配置

Docker 环境中，MySQL 配置通过 `docker-compose.yml` 的环境变量设置：

```yaml
mysql:
  environment:
    - MYSQL_ROOT_PASSWORD=root_password
    - MYSQL_DATABASE=zchat
    - MYSQL_USER=zchat
    - MYSQL_PASSWORD=zchat_password
```

生产环境中，请修改为强密码。

#### 传统环境配置

传统部署需要手动安装和配置 MySQL：

```bash
# 安装 MySQL
sudo apt install -y mysql-server

# 配置数据库
sudo mysql -e "CREATE DATABASE zchat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'zchat'@'localhost' IDENTIFIED BY 'your_password';"
sudo mysql -e "GRANT ALL PRIVILEGES ON zchat.* TO 'zchat'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

### MongoDB 配置

MongoDB 用于存储非结构化数据，如聊天记录和文档。

#### Docker 环境配置

Docker 环境中，MongoDB 配置通过 `docker-compose.yml` 的环境变量设置：

```yaml
mongodb:
  environment:
    - MONGO_INITDB_ROOT_USERNAME=zchat
    - MONGO_INITDB_ROOT_PASSWORD=zchat_password
    - MONGO_INITDB_DATABASE=zchat
```

#### 传统环境配置

传统部署需要手动安装和配置 MongoDB：

```bash
# 安装 MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y mongodb-org

# 启动服务
sudo systemctl start mongod
sudo systemctl enable mongod

# 创建用户和数据库
mongosh admin --eval "db.createUser({user: 'zchat', pwd: 'your_password', roles: [{role: 'readWrite', db: 'zchat'}]})"
```

## HTTPS 配置

### Docker 环境 HTTPS 配置

在 Docker 环境中，Nginx 容器负责 SSL 终结。

1. 获取有效 SSL 证书（推荐 Let's Encrypt）：

```bash
sudo certbot certonly --standalone -d your-domain.com
```

2. 将证书复制到 Docker 卷目录：

```bash
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./docker/nginx/ssl/
```

3. 修改 Nginx 配置中的服务器名称：

```bash
# 编辑 docker/nginx/nginx.conf
server_name your-domain.com;
```

4. 重启 Nginx 容器：

```bash
docker-compose restart nginx
```

5. 设置证书自动更新：

```bash
echo "0 3 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /path/to/zchat/docker/nginx/ssl/ && cp /etc/letsencrypt/live/your-domain.com/privkey.pem /path/to/zchat/docker/nginx/ssl/ && docker-compose restart nginx" | sudo tee -a /etc/crontab > /dev/null
```

### 传统环境 HTTPS 配置

在传统部署中，需要配置 Nginx 以支持 HTTPS：

1. 安装 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
```

2. 创建 Nginx 配置文件：

```bash
sudo nano /etc/nginx/sites-available/zchat.conf
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL 配置会由 certbot 自动添加

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/zchat/zchat/static/;
        expires 7d;
    }
}
```

3. 启用配置并获取证书：

```bash
sudo ln -s /etc/nginx/sites-available/zchat.conf /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

## 监控系统

Zchat 使用 Prometheus 和 Grafana 进行系统监控。

### Docker 环境监控配置

Docker 部署自动配置了 Prometheus 和 Grafana，不需要额外配置。

访问监控系统：
- Grafana: http://your-domain.com:3000 (默认凭据: admin/admin)

### 传统环境监控配置

1. 安装 Prometheus 和 Grafana：

```bash
# 安装 Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.50.1/prometheus-2.50.1.linux-amd64.tar.gz
tar xzf prometheus-2.50.1.linux-amd64.tar.gz
sudo mv prometheus-2.50.1.linux-amd64 /opt/prometheus

# 安装 Grafana
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install -y grafana
```

2. 配置 Prometheus：

创建 `/opt/prometheus/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'zchat'
    static_configs:
      - targets: ['localhost:5000']
```

3. 创建 Prometheus 服务：

```bash
sudo tee /etc/systemd/system/prometheus.service > /dev/null << EOF
[Unit]
Description=Prometheus Monitoring System
After=network.target

[Service]
User=prometheus
ExecStart=/opt/prometheus/prometheus --config.file=/opt/prometheus/prometheus.yml

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

4. 启动 Grafana 服务：

```bash
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

5. 配置 Grafana 数据源和仪表板：

通过 http://your-domain.com:3000 访问 Grafana，使用默认凭据 (admin/admin) 登录。

添加 Prometheus 数据源：
- URL: http://localhost:9090
- 访问方式: Server

## 维护操作

### 应用更新

#### Docker 环境更新

```bash
# 拉取最新代码
git pull

# 重建容器
docker-compose down
docker-compose up -d --build
```

#### 传统环境更新

```bash
# 拉取最新代码
git pull

# 停止应用
./prod_stop.sh

# 更新依赖
source .venv/bin/activate
pip install -r requirements.txt

# 启动应用
./prod_start.sh
```

### 数据备份

#### Docker 环境备份

```bash
# 创建备份目录
mkdir -p backups/$(date +%Y%m%d)

# MySQL 备份
docker-compose exec mysql mysqldump -u root -p$MYSQL_ROOT_PASSWORD zchat > backups/$(date +%Y%m%d)/mysql.sql

# MongoDB 备份
docker-compose exec mongodb mongodump --uri="mongodb://zchat:$MONGODB_PASSWORD@localhost:27017/zchat" --out=/tmp/backup
docker cp $(docker-compose ps -q mongodb):/tmp/backup backups/$(date +%Y%m%d)/mongodb

# Docker 卷备份
docker run --rm -v zchat-data:/source -v $PWD/backups/$(date +%Y%m%d):/backup alpine tar -czf /backup/zchat-data.tar.gz -C /source .
docker run --rm -v meilisearch-data:/source -v $PWD/backups/$(date +%Y%m%d):/backup alpine tar -czf /backup/meilisearch-data.tar.gz -C /source .
```

#### 传统环境备份

```bash
# 创建备份目录
mkdir -p /backup/zchat/$(date +%Y%m%d)

# 数据库备份
mysqldump -u root -p zchat > /backup/zchat/$(date +%Y%m%d)/mysql.sql
mongodump --uri="mongodb://zchat:your_password@localhost:27017/zchat" --out=/backup/zchat/$(date +%Y%m%d)/mongodb

# 应用文件备份
tar -czf /backup/zchat/$(date +%Y%m%d)/app_files.tar.gz -C /opt/zchat .
```

### 日志管理

#### Docker 环境日志

查看日志：

```bash
# 应用日志
docker-compose logs -f app

# Nginx 日志
docker-compose logs -f nginx

# 数据库日志
docker-compose logs -f mysql
docker-compose logs -f mongodb
```

#### 传统环境日志

日志文件位于：

- 应用日志: `/opt/zchat/log/`
- Nginx 日志: `/var/log/nginx/`

配置日志轮转：

```bash
sudo tee /etc/logrotate.d/zchat > /dev/null << EOF
/opt/zchat/log/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 zchat zchat
    sharedscripts
    postrotate
        systemctl reload zchat.service
    endscript
}
EOF
```

## 部署检查清单

### 前期准备

- [ ] 确认服务器规格满足需求（CPU、内存、存储）
- [ ] 确认域名已经注册并可以访问
- [ ] 确认防火墙已正确配置，开放必要的端口 (80, 443, 5000, 9090, 3000)
- [ ] 确认已安装必要的系统软件
- [ ] 确认已创建部署用户和必要的权限（传统部署）

### 代码部署

- [ ] 从版本控制系统获取最新代码
- [ ] 创建并激活 Python 虚拟环境（传统部署）
- [ ] 安装项目依赖
- [ ] 确认配置文件已经正确配置

### 环境配置

- [ ] 创建并配置数据库
- [ ] 运行数据库迁移脚本
- [ ] 配置 Nginx 反向代理
- [ ] 配置 SSL 证书
- [ ] 创建并启用服务（传统部署）
- [ ] 配置日志轮转

### 安全配置

- [ ] 生成并设置强密钥
- [ ] 检查并限制敏感目录的访问权限
- [ ] 配置 HTTPS 重定向
- [ ] 设置 HSTS 头部
- [ ] 配置 Content-Security-Policy
- [ ] 禁用不需要的 HTTP 方法
- [ ] 设置适当的 Cookie 策略（Secure, HttpOnly）

### 监控系统

- [ ] 安装并配置 Prometheus
- [ ] 安装并配置 Grafana
- [ ] 导入基础监控仪表板
- [ ] 创建 Zchat 专用监控仪表板
- [ ] 配置告警规则
- [ ] 配置告警通知通道（邮件、Slack 等）

### 生产环境测试

- [ ] 验证应用可以正常启动
- [ ] 测试 HTTPS 访问
- [ ] 测试关键功能路径
- [ ] 验证监控系统可以收集指标
- [ ] 验证监控告警可以正常触发
- [ ] 测试启动/停止脚本

### 备份和灾难恢复

- [ ] 配置数据库定期备份
- [ ] 确认备份策略和保留政策
- [ ] 验证备份可以成功恢复
- [ ] 编写灾难恢复流程文档

## 故障排除

### 常见问题

1. **应用无法连接数据库**:
   - Docker 环境：检查容器状态和网络连接
   - 传统环境：检查数据库服务是否运行
   - 确认环境变量和连接字符串配置正确

2. **HTTPS 配置问题**:
   - 检查证书文件是否有效和正确放置
   - 确认 Nginx 配置正确
   - 查看 Nginx 错误日志

3. **应用性能问题**:
   - 检查 Grafana 监控面板上的资源使用情况
   - 检查应用日志中的慢查询
   - 考虑增加资源或优化查询

### 重启服务

Docker 环境：

```bash
# 重启单个服务
docker-compose restart app

# 重启所有服务
docker-compose restart
```

传统环境：

```bash
# 重启应用
./prod_stop.sh
./prod_start.sh

# 重启 Nginx
sudo systemctl restart nginx
```

### 系统恢复

从备份恢复（Docker 环境）：

```bash
# MySQL 恢复
cat backups/20230101/mysql.sql | docker-compose exec -T mysql mysql -u root -p$MYSQL_ROOT_PASSWORD zchat

# MongoDB 恢复
docker cp backups/20230101/mongodb $(docker-compose ps -q mongodb):/tmp/
docker-compose exec mongodb mongorestore --uri="mongodb://zchat:$MONGODB_PASSWORD@localhost:27017/zchat" /tmp/mongodb

# 卷恢复
docker-compose down
docker volume rm zchat-data
docker volume create zchat-data
docker run --rm -v zchat-data:/target -v $PWD/backups/20230101:/backup alpine sh -c "tar -xzf /backup/zchat-data.tar.gz -C /target"
docker-compose up -d
```

从备份恢复（传统环境）：

```bash
# MySQL 恢复
mysql -u root -p zchat < /backup/zchat/20230101/mysql.sql

# MongoDB 恢复
mongorestore --uri="mongodb://zchat:your_password@localhost:27017/zchat" /backup/zchat/20230101/mongodb

# 应用文件恢复
rm -rf /opt/zchat/*
tar -xzf /backup/zchat/20230101/app_files.tar.gz -C /opt/zchat
```