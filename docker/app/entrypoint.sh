#!/bin/bash
set -e

# 等待MySQL和MongoDB准备就绪
echo "Waiting for MySQL..."
until nc -z mysql 3306; do
  sleep 1
done
echo "MySQL is ready!"

# 进一步验证MySQL连接是否真正可用
echo "Verifying MySQL connectivity..."
until python -c "
import pymysql
try:
    conn = pymysql.connect(
        host='mysql',
        user='zchat',
        password='zchat_password',
        db='zchat',
        charset='utf8mb4'
    )
    with conn.cursor() as cursor:
        cursor.execute('SELECT 1')
    conn.close()
    exit(0)
except Exception as e:
    print(f'Error connecting to MySQL: {e}')
    exit(1)
" >/dev/null 2>&1; do
  echo "Waiting for MySQL to be fully operational..."
  sleep 2
done
echo "MySQL connection confirmed!"

echo "Waiting for MongoDB..."
until nc -z mongodb 27017; do
  sleep 1
done
echo "MongoDB is ready!"

# Add verification that MongoDB is fully operational
echo "Verifying MongoDB data access..."
until python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb://zchat:zchat_password@mongodb:27017/')
    db = client['zchat']
    # Try a simple operation to verify database is responsive
    db.command('ping')
    exit(0)
except Exception as e:
    print(f'Error connecting to MongoDB: {e}')
    exit(1)
" >/dev/null 2>&1; do
  echo "Waiting for MongoDB to be fully operational..."
  sleep 2
done
echo "MongoDB connection confirmed!"

echo "Waiting for MeiliSearch..."
until nc -z meilisearch 7700; do
  sleep 1
done
echo "MeiliSearch is ready!"

# 设置默认日志级别
LOG_LEVEL=${LOG_LEVEL:-info}
echo "Setting log level to: $LOG_LEVEL"

# 启动Gunicorn服务器
echo "Starting Gunicorn server..."
exec gunicorn -b 0.0.0.0:5000 \
    --workers=1 \
    --threads=1 \
    --worker-class=gevent \
    --timeout 60 \
    --keep-alive 5 \
    --log-level $LOG_LEVEL \
    --access-logfile /app/log/gunicorn-access.log \
    --error-logfile /app/log/gunicorn-error.log \
    --capture-output \
    "zchat:create_app()"
