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

    if 'MONGODB_URI' in app.config:
        app.logger.info(f"MongoDB配置: {app.config['MONGODB_URI']}")

    @app.route('/api/system/db-status', methods=['GET'])
    def db_status_route():
        # 只允许内部访问
        from flask import request, jsonify
        client_ip = request.remote_addr
        if client_ip != '127.0.0.1' and not client_ip.startswith('10.') and not client_ip.startswith('172.'):
            return jsonify({"error": "Unauthorized"}), 403

        # 检查所有数据库状态
        status = {
            "mysql": {"status": "unknown"},
            "mongodb": {"status": "unknown"},
            "meilisearch": {"status": "unknown"},
        }

        # Status checking implementation can be added back when needed
        # Currently commented out in the original code

        return jsonify(status)
