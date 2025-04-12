#!/bin/bash

# Docker环境停止脚本

set -e

echo "========================================="
echo "     Zchat Docker环境停止脚本"
echo "========================================="

# 停止所有容器
echo "停止所有容器..."
docker-compose down

echo "已停止所有服务!"

# 如果需要彻底清理（包括卷），取消下面注释
# echo ""
# read -p "是否要删除所有数据卷? 这将删除所有数据! (y/N): " confirm
# if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
#     docker-compose down -v
#     echo "已删除所有容器和数据卷!"
# fi