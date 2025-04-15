import os

# 基本配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev')
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info')

# 数据库配置
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///zchat.db')
# SQLALCHEMY_TRACK_MODIFICATIONS = False

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

# MeiliSearch配置
MEILISEARCH_HOST = os.environ.get('MEILISEARCH_HOST', 'http://meilisearch:7700')
MEILISEARCH_KEY = os.environ.get('MEILISEARCH_KEY', 'aSampleMasterKey')
MEILISEARCH_TIMEOUT = int(os.environ.get('MEILISEARCH_TIMEOUT', '10'))

# 支付宝配置
ALIPAY_APP_ID = os.environ.get('ALIPAY_APP_ID', '')
ALIPAY_PRIVATE_KEY = os.environ.get('ALIPAY_PRIVATE_KEY', '')
ALIPAY_PUBLIC_KEY = os.environ.get('ALIPAY_PUBLIC_KEY', '')
ALIPAY_SANDBOX = os.environ.get('ALIPAY_SANDBOX', 'true') == 'true'  # 默认使用沙箱环境
ALIPAY_NOTIFY_URL = os.environ.get('ALIPAY_NOTIFY_URL', 'http://edu-paths.com/alipay/notify') # TODO update this
ALIPAY_RETURN_URL = os.environ.get('ALIPAY_RETURN_URL', 'http://edu-paths.com/alipay/return')

# HTTPS配置
PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')

# Docker环境标志
IS_DOCKER = os.environ.get('IS_DOCKER', 'false') == 'true'