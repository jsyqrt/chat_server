import click
from flask import current_app, g
import logging
import subprocess
import os
import time
import shutil
from pathlib import Path
from sqlalchemy import text, inspect
from datetime import datetime

# Re-export db to maintain compatibility with existing imports
# But do it in a way that avoids circular imports
from zchat.models.base import db

def init_app(app):
    """初始化所有数据库组件

    Args:
        app: Flask应用实例
    """
    if 'SQLALCHEMY_DATABASE_URI' in app.config:
        app.logger.info(f"MySQL配置: {app.config['SQLALCHEMY_DATABASE_URI']}")

    if 'DOCUMENT_STORE_TYPE' in app.config:
        app.logger.info(f"文档存储类型: {app.config['DOCUMENT_STORE_TYPE']}")
