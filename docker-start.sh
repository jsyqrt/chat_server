#!/bin/bash

# Docker环境启动脚本

set -e

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help                显示此帮助信息"
    echo "  --letsencrypt         使用Let's Encrypt签名的证书 (默认: 使用自签名证书)"
    echo "  --domain=<域名>       指定域名 (默认: localhost)"
    echo "  --log-level=<级别>    设置应用日志级别 (默认: info, 可选: debug, info, warning, error, critical)"
    echo "  --dev-mode            使用开发模式 (不将HTTP重定向到HTTPS)"
    echo ""
    echo "示例:"
    echo "  $0                    使用自签名证书启动，生产模式"
    echo "  $0 --letsencrypt      使用Let's Encrypt证书启动"
    echo "  $0 --letsencrypt --domain=example.com  指定域名并使用Let's Encrypt"
    echo "  $0 --log-level=debug  设置应用日志级别为debug"
    echo "  $0 --dev-mode         开发模式，允许HTTP直接访问"
    echo ""
}

echo "========================================="
echo "     Zchat Docker环境启动脚本"
echo "========================================="

# 检查是否使用Let's Encrypt
USE_LETSENCRYPT=false
DOMAIN_NAME="localhost"
LOG_LEVEL="info"
DEV_MODE=false

# 解析命令行参数
for arg in "$@"
do
    case $arg in
        --help)
        show_help
        exit 0
        ;;
        --letsencrypt)
        USE_LETSENCRYPT=true
        shift # 移除参数
        ;;
        --domain=*)
        DOMAIN_NAME="${arg#*=}"
        shift # 移除参数
        ;;
        --log-level=*)
        LOG_LEVEL="${arg#*=}"
        shift # 移除参数
        ;;
        --dev-mode)
        DEV_MODE=true
        shift # 移除参数
        ;;
        *)
        # 未知参数
        ;;
    esac
done

# 验证日志级别
case $LOG_LEVEL in
    debug|info|warning|error|critical)
        echo "应用日志级别设置为: $LOG_LEVEL"
        ;;
    *)
        echo "警告: 无效的日志级别 '$LOG_LEVEL'。使用默认值 'info'"
        LOG_LEVEL="info"
        ;;
esac

# 检查是否已安装 Docker 和 Docker Compose
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
    echo "错误: 需要安装 Docker 和 Docker Compose"
    echo "请参考 https://docs.docker.com/get-docker/ 安装 Docker"
    echo "请参考 https://docs.docker.com/compose/install/ 安装 Docker Compose"
    exit 1
fi

# 如果使用Let's Encrypt，需要获取域名
if [ "$USE_LETSENCRYPT" = true ] && [ "$DOMAIN_NAME" = "localhost" ]; then
    read -p "请输入您的域名 (例如: example.com): " DOMAIN_NAME
    if [ -z "$DOMAIN_NAME" ] || [ "$DOMAIN_NAME" = "localhost" ]; then
        echo "错误: 使用Let's Encrypt需要有效的域名"
        exit 1
    fi
fi

# 检查SSL证书
if [ ! -f "./docker/nginx/ssl/fullchain.pem" ] || [ ! -f "./docker/nginx/ssl/privkey.pem" ]; then
    # 创建证书目录
    mkdir -p ./docker/nginx/ssl

    if [ "$USE_LETSENCRYPT" = true ]; then
        echo "SSL证书未找到"
        echo "将配置Let's Encrypt证书..."

        mkdir -p ./docker/letsencrypt

        # 创建docker-compose.certbot.yml文件
        cat > docker-compose.certbot.yml << EOL
version: '3.8'
services:
  certbot:
    image: certbot/certbot
    container_name: certbot
    volumes:
      - ./docker/letsencrypt:/etc/letsencrypt
      - ./docker/nginx/ssl:/ssl
      - ./certbot-webroot:/var/www/html
    command: certonly --webroot --webroot-path=/var/www/html --email admin@${DOMAIN_NAME} --agree-tos --no-eff-email -d ${DOMAIN_NAME}
EOL

        # 创建临时Nginx配置用于证书申请
        mkdir -p ./certbot-webroot/.well-known/acme-challenge

        cat > docker-compose.certbot-nginx.yml << EOL
version: '3.8'
services:
  certbot-nginx:
    image: nginx:alpine
    container_name: certbot-nginx
    ports:
      - "80:80"
    volumes:
      - ./certbot-webroot:/var/www/html
    command: nginx -g 'daemon off;'
EOL

        echo "启动临时Nginx服务器以完成域名验证..."
        docker-compose -f docker-compose.certbot-nginx.yml up -d

        echo "请确保您的域名 ${DOMAIN_NAME} 已正确解析到此服务器，并且端口80已开放"
        read -p "按回车键继续申请Let's Encrypt证书..." CONTINUE

        echo "申请Let's Encrypt证书..."
        docker-compose -f docker-compose.certbot.yml run --rm certbot

        echo "停止临时Nginx服务器..."
        docker-compose -f docker-compose.certbot-nginx.yml down

        # 如果证书生成成功，复制到nginx ssl目录
        if [ -f "./docker/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ] && [ -f "./docker/letsencrypt/live/${DOMAIN_NAME}/privkey.pem" ]; then
            cp "./docker/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ./docker/nginx/ssl/
            cp "./docker/letsencrypt/live/${DOMAIN_NAME}/privkey.pem" ./docker/nginx/ssl/
            echo "Let's Encrypt证书已成功申请并安装"

            # 添加证书自动续期的cron任务
            echo "配置证书自动续期..."
            (crontab -l 2>/dev/null; echo "0 3 * * * docker run --rm -v $(pwd)/docker/letsencrypt:/etc/letsencrypt -v $(pwd)/certbot-webroot:/var/www/html certbot/certbot renew --webroot --webroot-path=/var/www/html && cp $(pwd)/docker/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem $(pwd)/docker/nginx/ssl/ && cp $(pwd)/docker/letsencrypt/live/${DOMAIN_NAME}/privkey.pem $(pwd)/docker/nginx/ssl/ && docker exec zchat-nginx nginx -s reload") | crontab -
            echo "已添加证书自动续期的计划任务"
        else
            echo "错误: 无法申请Let's Encrypt证书。请检查域名配置和网络连接。"
            exit 1
        fi

        # 清理临时文件
        rm -f docker-compose.certbot.yml
        rm -f docker-compose.certbot-nginx.yml
    else
        echo "警告: SSL证书未找到"
        echo "创建自签名证书用于开发..."

        # 生成自签名证书
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ./docker/nginx/ssl/privkey.pem \
            -out ./docker/nginx/ssl/fullchain.pem \
            -subj "/C=CN/ST=State/L=City/O=Organization/OU=Unit/CN=localhost"

        echo "自签名证书已创建。生产环境请替换为有效的SSL证书。"
    fi
else
    echo "找到现有SSL证书，将继续使用"
fi

# 创建 .htpasswd 文件用于 metrics 认证
if [ ! -f "./docker/nginx/.htpasswd" ]; then
    echo "创建 metrics 认证文件..."
    echo "admin:$(openssl passwd -apr1 admin)" > ./docker/nginx/.htpasswd
    echo "默认 metrics 认证: 用户名=admin, 密码=admin"
fi

# 创建必要的目录
mkdir -p ./docker/mysql/init
mkdir -p ./docker/mongodb/init

# 确保初始化脚本存在
if [ ! -f "./docker/mysql/init/01-schema.sql" ]; then
    echo "创建MySQL初始化脚本..."
    cat > ./docker/mysql/init/01-schema.sql << 'EOL'
-- 创建数据库表结构
CREATE DATABASE IF NOT EXISTS zchat;
USE zchat;

-- 确保用户存在并有正确权限
CREATE USER IF NOT EXISTS 'zchat'@'%' IDENTIFIED BY 'zchat_password';
GRANT ALL PRIVILEGES ON zchat.* TO 'zchat'@'%';
FLUSH PRIVILEGES;
EOL
fi

if [ ! -f "./docker/mongodb/init/01-init.js" ]; then
    echo "创建MongoDB初始化脚本..."
    cat > ./docker/mongodb/init/01-init.js << 'EOL'
// 在admin数据库中进行认证
db = db.getSiblingDB('admin');
db.auth('zchat', 'zchat_password');

// 创建和初始化zchat数据库
db = db.getSiblingDB('zchat');

// 创建文档集合
if (!db.getCollectionNames().includes('documents')) {
    db.createCollection('documents');
    print("Created 'documents' collection");
}

// 检查并删除可能存在的文本索引以避免冲突
var indexes = db.documents.getIndexes();
for (var i = 0; i < indexes.length; i++) {
    var idx = indexes[i];
    if (idx.key && idx.key._fts) {
        print("Dropping existing text index: " + idx.name);
        db.documents.dropIndex(idx.name);
    }
}

// 为documents集合创建索引
db.documents.createIndex({ "id": 1 }, { unique: true });
db.documents.createIndex({ "content": "text", "metadata.title": "text" });
db.documents.createIndex({ "type": 1 });
db.documents.createIndex({ "created_at": 1 });
db.documents.createIndex({ "updated_at": 1 });
db.documents.createIndex({ "metadata.user_id": 1 });

print("Initialized MongoDB database and collections successfully");
EOL
fi

# 更新Nginx配置以使用域名
echo "更新Nginx配置以使用域名 ${DOMAIN_NAME}..."
if [ "$DOMAIN_NAME" = "localhost" ]; then
    # 如果是localhost，确保使用"localhost"作为server_name
    sed -i.bak "s/server_name [^;]*;/server_name localhost;/g" ./docker/nginx/nginx.conf.prod
    sed -i.bak "s/server_name [^;]*;/server_name localhost;/g" ./docker/nginx/nginx.conf.dev
else
    # 如果是其他域名，更新server_name
    sed -i.bak "s/server_name [^;]*;/server_name ${DOMAIN_NAME};/g" ./docker/nginx/nginx.conf.prod
    sed -i.bak "s/server_name [^;]*;/server_name ${DOMAIN_NAME};/g" ./docker/nginx/nginx.conf.dev
fi

# 根据部署模式设置环境变量
if [ "$DEV_MODE" = true ]; then
    echo "配置开发模式: 启用HTTP直接访问..."
    DEPLOY_MODE="dev"
else
    echo "配置生产模式: 强制HTTPS..."
    DEPLOY_MODE="prod"
fi

echo "SF_ZCHAT_API_KEY: ${SF_ZCHAT_API_KEY:-UNKNOWN}"

# 构建和启动容器
echo "启动 Docker 容器..."
# 创建临时 docker-compose-override.yml 用于注入环境变量
cat > docker-compose.override.yml << EOL
version: '3.8'
services:
  app:
    environment:
      - LOG_LEVEL=${LOG_LEVEL}
      - SF_ZCHAT_API_KEY=${SF_ZCHAT_API_KEY:-UNKNOWN}
  nginx:
    environment:
      - DEPLOY_MODE=${DEPLOY_MODE}
EOL

# 导出环境变量以便Docker Compose使用
export DEPLOY_MODE

docker-compose up -d --build

# 删除临时 override 文件
rm -f docker-compose.override.yml

# 检查服务状态
echo "检查服务状态..."
sleep 10
docker-compose ps

echo ""
echo "启动完成! 您现在可以访问:"
echo "- 应用: https://${DOMAIN_NAME}"
if [ "$DEV_MODE" = true ]; then
    echo "  开发模式: 您也可以通过 http://${DOMAIN_NAME} 直接访问"
fi
echo "- Grafana: http://${DOMAIN_NAME}:3000 (默认用户名/密码: admin/admin)"
echo "- 应用日志级别: ${LOG_LEVEL}"
echo "- 部署模式: $([ "$DEV_MODE" = true ] && echo "开发模式" || echo "生产模式")"
echo ""
echo "可以使用以下命令查看日志:"
echo "  docker-compose logs -f app"
echo "  docker-compose logs -f nginx"
echo "  docker-compose logs -f mysql"
echo "  docker-compose logs -f mongodb"
echo "  docker-compose logs -f meilisearch"

echo ""
echo "========================================="
echo "     数据库管理"
echo "========================================="
echo "如果遇到数据库相关错误，您可以使用以下命令进行修复和排查："
echo ""
echo "1. 查看应用日志:"
echo "   docker-compose logs -f app"
echo ""
echo "2. 进入容器执行数据库修复命令:"
echo "   docker exec -it zchat-app bash"
echo "   cd /app && python scripts/db_manager.py fix"
echo ""
echo "3. 检查数据库状态:"
echo "   docker exec -it zchat-app bash -c 'cd /app && python scripts/db_manager.py status'"
echo ""
echo "4. 如果遇到MongoDB索引冲突，可以使用以下命令修复:"
echo "   docker exec -it zchat-app bash"
echo "   cd /app && python scripts/db_manager.py init-mongo"
echo ""
echo "5. 如果需要重置数据库迁移:"
echo "   docker exec -it zchat-app bash"
echo "   cd /app && python scripts/db_manager.py reset-migrations --force"
echo ""
echo "详细文档请参考:"
echo "  docs/database_management.md"
echo "========================================="