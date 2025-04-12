#!/bin/bash

# 证书手动续期脚本

set -e

echo "========================================="
echo "     Zchat 证书管理工具"
echo "========================================="

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项] [域名]"
    echo ""
    echo "选项:"
    echo "  -h, --help            显示此帮助信息"
    echo "  -r, --renew           续期Let's Encrypt证书 (默认操作)"
    echo "  -s, --self-signed     重新生成自签名证书"
    echo ""
    echo "示例:"
    echo "  $0                    尝试续期当前域名的Let's Encrypt证书"
    echo "  $0 example.com        为指定域名续期Let's Encrypt证书"
    echo "  $0 --self-signed      重新生成自签名证书"
    echo ""
}

# 默认操作
OPERATION="renew"
DOMAIN_NAME=""

# 解析命令行参数
for arg in "$@"
do
    case $arg in
        -h|--help)
        show_help
        exit 0
        ;;
        -r|--renew)
        OPERATION="renew"
        shift
        ;;
        -s|--self-signed)
        OPERATION="self-signed"
        shift
        ;;
        *)
        if [ -z "$DOMAIN_NAME" ] && [[ ! "$arg" =~ ^- ]]; then
            DOMAIN_NAME="$arg"
        fi
        ;;
    esac
done

# 如果是自签名证书操作
if [ "$OPERATION" = "self-signed" ]; then
    echo "将生成新的自签名证书..."

    # 创建证书目录
    mkdir -p ./docker/nginx/ssl

    # 生成自签名证书
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ./docker/nginx/ssl/privkey.pem \
        -out ./docker/nginx/ssl/fullchain.pem \
        -subj "/C=CN/ST=State/L=City/O=Organization/OU=Unit/CN=localhost"

    echo "自签名证书已重新生成"

    # 重新加载nginx配置
    if docker ps -q -f name=zchat-nginx > /dev/null; then
        echo "重新加载 Nginx 配置..."
        docker exec zchat-nginx nginx -s reload
        echo "Nginx 已重新加载"
    else
        echo "提示: Nginx 容器未运行，无需重新加载配置"
    fi

    exit 0
fi

# 以下是Let's Encrypt证书续期流程

# 如果没有指定域名，尝试从nginx配置获取
if [ -z "$DOMAIN_NAME" ]; then
    # 尝试从nginx配置中获取域名
    DOMAIN_NAME=$(grep -oP 'server_name \K[^;]+' ./docker/nginx/nginx.conf)
    DOMAIN_NAME=$(echo $DOMAIN_NAME | tr -d '[:space:]')

    if [ -z "$DOMAIN_NAME" ] || [ "$DOMAIN_NAME" = "localhost" ]; then
        echo "错误: 无法确定域名，或当前使用的是本地开发环境 (localhost)"
        echo "如需为特定域名续期Let's Encrypt证书，请提供域名作为参数:"
        echo "  ./renew-cert.sh example.com"
        echo "如需重新生成自签名证书，请使用:"
        echo "  ./renew-cert.sh --self-signed"
        exit 1
    fi
fi

echo "为域名 $DOMAIN_NAME 更新 Let's Encrypt 证书"

# 检查Let's Encrypt目录是否存在
if [ ! -d "./docker/letsencrypt/live/${DOMAIN_NAME}" ]; then
    echo "错误: 找不到域名 ${DOMAIN_NAME} 的Let's Encrypt证书"
    echo "可能从未为此域名申请过Let's Encrypt证书，或使用的是自签名证书"
    echo "请先使用 docker-start.sh --letsencrypt --domain=${DOMAIN_NAME} 申请证书"
    exit 1
fi

# 确保目录存在
mkdir -p ./docker/letsencrypt
mkdir -p ./certbot-webroot/.well-known/acme-challenge

# 运行certbot进行证书更新
echo "运行 certbot renew..."
docker run --rm \
    -v $(pwd)/docker/letsencrypt:/etc/letsencrypt \
    -v $(pwd)/certbot-webroot:/var/www/html \
    certbot/certbot renew --webroot --webroot-path=/var/www/html

# 检查更新结果
if [ -f "./docker/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ] && [ -f "./docker/letsencrypt/live/${DOMAIN_NAME}/privkey.pem" ]; then
    # 复制新证书到nginx目录
    cp "./docker/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ./docker/nginx/ssl/
    cp "./docker/letsencrypt/live/${DOMAIN_NAME}/privkey.pem" ./docker/nginx/ssl/

    # 重新加载nginx配置
    echo "更新证书文件并重新加载 Nginx 配置..."
    docker exec zchat-nginx nginx -s reload

    echo "证书已成功更新并应用"
else
    echo "警告: 无法找到更新后的证书文件。请检查Let's Encrypt日志获取更多信息。"
fi

echo "证书更新过程完成"