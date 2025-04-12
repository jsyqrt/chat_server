FROM nginx:1.25

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 不复制配置文件，将通过挂载卷提供
# 注：配置文件将通过docker-compose卷映射提供

# 创建 SSL 证书目录
RUN mkdir -p /etc/nginx/ssl

# 暴露HTTP和HTTPS端口
EXPOSE 80 443