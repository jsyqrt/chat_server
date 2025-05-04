import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from logging.handlers import RotatingFileHandler
import redis

def create_app(test_config=None, tool_mode=False):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        config_path = os.path.join(app.root_path, 'config.py')
        if os.path.exists(config_path):
            app.config.from_pyfile(config_path)

        # 从环境变量加载文档存储配置
        document_store_type = os.environ.get('DOCUMENT_STORE_TYPE', 'mysql')
        app.config['DOCUMENT_STORE_TYPE'] = document_store_type

        # 文档存储配置
        document_store_config = {}

        if document_store_type == 'mysql':
            # MySQL文档存储配置
            if all(key in os.environ for key in ['MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_HOST', 'MYSQL_PORT']):
                document_store_config.update({
                    'host': os.environ.get('MYSQL_HOST', 'localhost'),
                    'port': int(os.environ.get('MYSQL_PORT', '3306')),
                    'user': os.environ.get('MYSQL_USER', 'zchat'),
                    'password': os.environ.get('MYSQL_PASSWORD', 'zchat_password'),
                    'db_name': os.environ.get('MYSQL_DB', 'zchat')
                })
        elif document_store_type == 'mongodb':
            # MongoDB文档存储配置
            if all(key in os.environ for key in ['MONGODB_USER', 'MONGODB_PASSWORD', 'MONGODB_HOST', 'MONGODB_PORT']):
                document_store_config.update({
                    'host': os.environ.get('MONGODB_HOST', 'localhost'),
                    'port': int(os.environ.get('MONGODB_PORT', '27017')),
                    'username': os.environ.get('MONGODB_USER', 'zchat'),
                    'password': os.environ.get('MONGODB_PASSWORD', 'zchat_password'),
                    'db_name': os.environ.get('MONGODB_DB', 'zchat'),
                    'auth_source': os.environ.get('MONGODB_AUTH_SOURCE', 'admin')
                })

        app.config['DOCUMENT_STORE_CONFIG'] = document_store_config

        # 记录当前选择的文档存储类型
        app.logger.info(f"文档存储类型设置为: {document_store_type}")
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # 确保应用启动时标记为未关闭状态
    app.config['SERVER_SHUTTING_DOWN'] = False

    # 注册应用关闭时的处理函数 - 使用Flask 3.x兼容方式
    import atexit

    @atexit.register
    def prepare_shutdown():
        with app.app_context():
            app.config['SERVER_SHUTTING_DOWN'] = True
            app.logger.info("应用正在关闭，已设置关闭标志...")

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

    # 如果是工具模式，这里提前返回应用实例
    if tool_mode:
        app.logger.info("以工具模式启动应用，跳过蓝图注册和非必要组件")
        return app

    # 健康检查端点，用于监控和负载均衡
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    # 初始化Redis连接
    redis_host = app.config.get('REDIS_HOST', 'redis')
    redis_port = app.config.get('REDIS_PORT', 6379)
    redis_password = app.config.get('REDIS_PASSWORD', None)
    redis_db = app.config.get('REDIS_DB', 0)

    try:
        app.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True
        )
        # 测试Redis连接
        app.redis.ping()
        app.logger.info(f"Redis连接成功: {redis_host}:{redis_port}")
    except Exception as e:
        app.logger.error(f"Redis连接失败: {str(e)}")
        app.logger.warning("应用将在没有Redis功能的情况下继续运行，某些功能可能不可用")
        app.redis = None

    # 数据库初始化，按以下顺序处理，避免循环导入
    # 1. 初始化 SQLAlchemy - 这必须首先完成
    from zchat.models.base import init_db
    init_db(app)

    # 2. 确保所有模型已被导入，这对Flask-Migrate非常重要
    import zchat.models

    # 3. 数据库组件
    from . import db
    db.init_app(app)

    from . import storage
    storage.init_app(app)

    # 4. 初始化监控模块
    try:
        from . import monitoring
        monitoring.init_app(app)
        app.logger.info("监控模块初始化成功")
    except Exception as e:
        app.logger.error(f"监控模块初始化失败: {str(e)}")
        app.logger.warning("应用将在没有监控功能的情况下继续运行")

    # 5. 初始化支付宝配置
    try:
        from zchat.utils.alipay_utils import alipay_config
        alipay_config.init_app(app)
        app.logger.info("支付宝模块初始化成功")
    except Exception as e:
        app.logger.error(f"支付宝模块初始化失败: {str(e)}")
        app.logger.warning("应用将在没有支付宝功能的情况下继续运行")

    # 6. 注册所有蓝图

    # 认证蓝图
    from . import auth
    app.register_blueprint(auth.bp)
    auth.init_verification_code_dict(app)
    auth.init_app(app)

    # 邮件服务
    from . import mail
    mail.init_app(app)

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

    # 支付宝支付蓝图
    from . import alipay
    alipay.init_app(app)

    # 邀请系统蓝图
    from . import invitation
    invitation.init_app(app)

    # 官网页面蓝图
    from . import website
    app.register_blueprint(website.bp)

    return app
