from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 创建全局SQLAlchemy实例
db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """初始化SQLAlchemy数据库实例

    Args:
        app: Flask应用实例
    """
    db.init_app(app)
    migrate.init_app(app, db)

    # 在应用上下文中测试连接
    with app.app_context():
        try:
            engine = db.get_engine()
            connection = engine.connect()
            connection.close()
            app.logger.info("SQLAlchemy连接测试成功")
        except Exception as e:
            app.logger.error(f"SQLAlchemy连接测试失败: {str(e)}")
            raise