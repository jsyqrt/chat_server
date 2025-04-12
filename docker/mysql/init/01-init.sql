-- MySQL初始化脚本
-- 注意：数据库和用户已由Docker环境变量自动创建:
-- - MYSQL_DATABASE=zchat
-- - MYSQL_USER=zchat
-- - MYSQL_PASSWORD=zchat_password

-- 确保使用UTF-8编码
ALTER DATABASE zchat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 注意：表结构由Flask-Migrate(Alembic)管理
-- 请勿在此处手动创建表，应使用以下命令：
-- flask db init      # 初始化迁移
-- flask db migrate   # 创建迁移脚本
-- flask db upgrade   # 应用迁移到数据库