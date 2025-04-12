FROM python:3.11-slim-buster

WORKDIR /app

# 使用Debian官方源（移除特定镜像源配置）
# 如果需要加速，可以考虑使用其他稳定的镜像源，例如：
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list \
    && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    default-mysql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制入口点脚本
COPY docker/app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露应用端口
EXPOSE 5000

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=zchat

# 使用入口点脚本
ENTRYPOINT ["/entrypoint.sh"]