import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask


def init_app(app: Flask) -> None:
    """配置应用日志系统

    为Flask应用配置日志，包括应用日志、错误日志、Werkzeug日志和SQLAlchemy日志
    所有级别的日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）都输出到同一个文件中

    Args:
        app: Flask应用实例
    """
    # 检查是否在Docker环境中运行
    is_docker = app.config.get('IS_DOCKER', False)

    if is_docker:
        # Docker环境使用/app/log目录
        log_dir = '/app/log'
    else:
        # 非Docker环境使用app.root_path/log目录
        log_dir = os.path.join(app.root_path, 'log')

    os.makedirs(log_dir, exist_ok=True)
    print(f'log_dir: {log_dir}')

    # 创建格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    # 创建文件处理器 - 应用日志
    app_log_file = os.path.join(log_dir, 'app.log')
    app_file_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    app_file_handler.setFormatter(formatter)
    # 设置文件处理器级别为DEBUG，确保所有级别的日志都被捕获
    app_file_handler.setLevel(logging.DEBUG)

    # 配置根日志器，这样所有未指定日志器的日志也能被捕获
    root_log_file = os.path.join(log_dir, 'root.log')
    root_file_handler = RotatingFileHandler(
        root_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    root_file_handler.setFormatter(formatter)
    root_file_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(root_file_handler)

    # 配置 Flask 应用日志
    app.logger.setLevel(logging.DEBUG)
    # 移除可能存在的默认处理器
    for handler in app.logger.handlers:
        app.logger.removeHandler(handler)
    app.logger.addHandler(app_file_handler)

    # 配置 Werkzeug 日志 (Flask 的 WSGI 接口)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.DEBUG)
    # 移除可能存在的默认处理器
    for handler in werkzeug_logger.handlers:
        werkzeug_logger.removeHandler(handler)
    werkzeug_logger.addHandler(root_file_handler)

    # 配置 SQLAlchemy 日志 (数据库 ORM)
    sqlalchemy_logger = logging.getLogger('sqlalchemy')
    sqlalchemy_logger.setLevel(logging.DEBUG)
    # 移除可能存在的默认处理器
    for handler in sqlalchemy_logger.handlers:
        sqlalchemy_logger.removeHandler(handler)
    sqlalchemy_logger.addHandler(root_file_handler)

    # 记录其他常用日志器
    loggers = [
        logging.getLogger('flask'),
        logging.getLogger('urllib3'),
        logging.getLogger('requests')
    ]
    for logger in loggers:
        logger.setLevel(logging.DEBUG)
        # 移除可能存在的默认处理器
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.addHandler(root_file_handler)

    app.logger.info("应用日志配置完成 - 所有级别日志均输出到同一文件")