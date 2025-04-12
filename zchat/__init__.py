import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from logging.handlers import RotatingFileHandler

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        config_path = os.path.join(app.root_path, 'config.py')
        if os.path.exists(config_path):
            app.config.from_pyfile(config_path)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # 应用ProxyFix中间件以处理反向代理头部
    # 参数分别表示: X-Forwarded-For, X-Forwarded-Host, X-Forwarded-Proto, X-Forwarded-Port, X-Forwarded-Prefix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1, x_prefix=1)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # 配置应用日志
    try:
        from . import logger
        logger.init_app(app)
    except ImportError:
        print("No logging module found")

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    # 健康检查端点，用于监控和负载均衡
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    # 数据库初始化，按以下顺序处理，避免循环导入
    # 1. 初始化 SQLAlchemy - 这必须首先完成
    from zchat.models.base import init_db
    init_db(app)

    # 1.5 确保所有模型已被导入，这对Flask-Migrate非常重要
    import zchat.models

    # 2. 数据库组件（MongoDB + SQLAlchemy迁移）
    from . import db
    db.init_app(app)

    from . import storage
    storage.init_app(app)

    # 3. 初始化 MeiliSearch
    try:
        from . import meili
        meili.init_app(app)
    except Exception as e:
        app.logger.error(f"MeiliSearch 初始化失败: {str(e)}")
        app.logger.warning("应用将在没有MeiliSearch的情况下继续运行")

    # 4. 初始化监控模块
    try:
        from . import monitoring
        monitoring.init_app(app)
        app.logger.info("监控模块初始化成功")
    except Exception as e:
        app.logger.error(f"监控模块初始化失败: {str(e)}")
        app.logger.warning("应用将在没有监控功能的情况下继续运行")

    # 5. 注册所有蓝图

    # 认证蓝图
    from . import auth
    app.register_blueprint(auth.bp)
    auth.init_verification_code_dict(app)
    auth.init_app(app)

    # 用户蓝图
    from . import user
    app.register_blueprint(user.bp)

    # 头像管理
    from . import avatar
    avatar.init_app(app)

    # 客服模块
    from . import customer_service
    app.register_blueprint(customer_service.bp)

    # 路径蓝图
    from . import roadmap
    app.register_blueprint(roadmap.bp)

    # 评估蓝图
    from . import assessment
    app.register_blueprint(assessment.bp)

    # 工作蓝图
    from . import job
    app.register_blueprint(job.bp)

    # 简历蓝图
    from . import resume
    app.register_blueprint(resume.bp)

    # AI聊天蓝图
    from .aichat import chat, chat_stream
    app.register_blueprint(chat.bp)
    app.register_blueprint(chat_stream.bp)

    # 积分系统蓝图
    from . import points
    points.init_app(app)

    # 邀请系统蓝图
    from . import invitation
    invitation.init_app(app)

    # 官网页面蓝图
    from . import website
    app.register_blueprint(website.bp)

    return app
