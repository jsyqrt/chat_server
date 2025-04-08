import os

from flask import Flask

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev', # TODO override this with thevalue in config.py
        JWT_SECRET_KEY='dev', # TODO override this with thevalue in config.py
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, 'zchat.sqlite'),
        DOCUMENT_STORE_TYPE='sqlite',
        DOCUMENT_STORE_CONFIG={
            'db_path': os.path.join(app.instance_path, 'document_store.db')
        },
        # 保留原有的MeiliSearch配置，以便兼容
        MEILISEARCH_HOST="http://localhost:7700",
        MEILISEARCH_KEY="aSampleMasterKey",
        # LIVEKIT_HOST="http://localhost:7880",
        # LIVEKIT_API_KEY="devkey",
        # LIVEKIT_API_SECRET="secret",
        # LIVEKIT_RECORDS_PATH="livekit/records/",
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    from . import db
    db.init_app(app)
    db.db.init_app(app)

    from . import websocket
    websocket.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)
    auth.init_verification_code_dict(app)
    auth.init_app(app)

    # from . import admin
    # app.register_blueprint(admin.bp)

    from . import user
    app.register_blueprint(user.bp)

    from . import avatar
    avatar.init_app(app)

    # from . import chat
    # app.register_blueprint(chat.bp)

    # from . import appointment
    # app.register_blueprint(appointment.bp)

    from . import customer_service
    app.register_blueprint(customer_service.bp)

    from . import meili
    meili.init_app(app)

    from . import roadmap
    app.register_blueprint(roadmap.bp)

    from . import assessment
    app.register_blueprint(assessment.bp)

    from . import job
    app.register_blueprint(job.bp)

    from . import resume
    app.register_blueprint(resume.bp)

    from .aichat import chat, chat_stream
    app.register_blueprint(chat.bp)
    app.register_blueprint(chat_stream.bp)

    # 注册积分系统相关蓝图
    from . import points
    points.init_app(app)

    # 注册邀请系统相关蓝图
    from . import invitation
    invitation.init_app(app)

    # 初始化定时任务调度器（用于检查订阅过期和积分过期）
    from . import scheduler
    scheduler.init_app(app)

    return app
