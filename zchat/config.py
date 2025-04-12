import os

# 基本配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev')
FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info')

# 数据库配置
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///zchat.db')
# SQLALCHEMY_TRACK_MODIFICATIONS = False

# MongoDB配置
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://zchat:zchat_password@mongodb:27017/')
MONGODB_DB = os.environ.get('MONGODB_DB', 'zchat')
MONGODB_DOCS_COLLECTION = os.environ.get('MONGODB_DOCS_COLLECTION', 'documents')

# 文档存储配置
# 如果MongoDB可用，则使用MongoDB，否则使用SQLite
try:
    import pymongo
    # 尝试连接MongoDB
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
    client.server_info()  # 强制连接检查
    DOCUMENT_STORE_TYPE = os.environ.get('DOCUMENT_STORE_TYPE', 'mongodb')
    DOCUMENT_STORE_CONFIG = {
        'uri': MONGODB_URI,
        'db_name': MONGODB_DB
    }
except (ImportError, pymongo.errors.ServerSelectionTimeoutError):
    # 如果无法连接MongoDB，使用SQLite
    DOCUMENT_STORE_TYPE = os.environ.get('DOCUMENT_STORE_TYPE', 'sqlite')
    DOCUMENT_STORE_CONFIG = {
        'db_path': os.environ.get('DOCUMENT_STORE_PATH', 'instance/document_store.db')
    }

# MeiliSearch配置
MEILISEARCH_HOST = os.environ.get('MEILISEARCH_HOST', 'http://meilisearch:7700')
MEILISEARCH_KEY = os.environ.get('MEILISEARCH_KEY', 'aSampleMasterKey')
MEILISEARCH_TIMEOUT = int(os.environ.get('MEILISEARCH_TIMEOUT', '10'))

# HTTPS配置
PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')

# Docker环境标志
IS_DOCKER = os.environ.get('IS_DOCKER', 'false') == 'true'