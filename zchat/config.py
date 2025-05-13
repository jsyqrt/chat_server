import os

# 基本配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev')
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info')

# 数据库配置
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///zchat.db')
# SQLALCHEMY_TRACK_MODIFICATIONS = False

# Redis配置
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

# 文档存储配置
# 默认使用MySQL，如果设置了其他存储类型则使用其他存储类型
DOCUMENT_STORE_TYPE = os.environ.get('DOCUMENT_STORE_TYPE', 'mysql')
if DOCUMENT_STORE_TYPE == 'mysql':
    DOCUMENT_STORE_CONFIG = {
        'host': os.environ.get('MYSQL_HOST', 'mysql'),
        'port': int(os.environ.get('MYSQL_PORT', '3306')),
        'user': os.environ.get('MYSQL_USER', 'zchat'),
        'password': os.environ.get('MYSQL_PASSWORD', 'zchat_password'),
        'db_name': os.environ.get('MYSQL_DB', 'zchat')
    }
else:
    # 如果需要使用SQLite存储
    DOCUMENT_STORE_TYPE = 'sqlite'
    DOCUMENT_STORE_CONFIG = {
        'db_path': os.environ.get('DOCUMENT_STORE_PATH', 'instance/document_store.db')
    }

# 邮件服务配置
MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.voylead.com')
MAIL_PORT=int(os.environ.get('MAIL_PORT', 465))
MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'false').lower() in ['true', 'on', '1']  # 使用465端口时禁用TLS
MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', 'on', '1']  # 使用465端口时启用SSL
MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'noreply@voylead.com')
MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@voylead.com')

# 网站URL，用于生成邮件中的链接
SITE_URL=os.environ.get('SITE_URL', '')

# OAuth配置
GOOGLE_CLIENT_ID=os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET=os.environ.get('GOOGLE_CLIENT_SECRET', '')
GITHUB_CLIENT_ID=os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET=os.environ.get('GITHUB_CLIENT_SECRET', '')

# 支付宝配置
ALIPAY_APP_ID = os.environ.get('ALIPAY_APP_ID', '')
ALIPAY_PRIVATE_KEY = os.environ.get('ALIPAY_PRIVATE_KEY', '')
ALIPAY_PUBLIC_KEY = os.environ.get('ALIPAY_PUBLIC_KEY', '')
ALIPAY_GATEWAY_URL = os.environ.get('ALIPAY_GATEWAY_URL', '')
ALIPAY_NOTIFY_URL = os.environ.get('ALIPAY_NOTIFY_URL', '')
ALIPAY_RETURN_URL = os.environ.get('ALIPAY_RETURN_URL', '')

# Paddle支付配置
PADDLE_VENDOR_ID = os.environ.get('PADDLE_VENDOR_ID', '')
PADDLE_API_KEY = os.environ.get('PADDLE_API_KEY', '')
PADDLE_PUBLIC_KEY = os.environ.get('PADDLE_PUBLIC_KEY', '')
PADDLE_SANDBOX_MODE = os.environ.get('PADDLE_SANDBOX_MODE', 'true') == 'true'
PADDLE_WEBHOOK_URL = os.environ.get('PADDLE_WEBHOOK_URL', '')

# HTTPS配置
PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')

# Docker环境标志
IS_DOCKER = os.environ.get('IS_DOCKER', 'false') == 'true'