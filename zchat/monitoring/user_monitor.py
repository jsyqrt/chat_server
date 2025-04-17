"""
用户活跃度监控工具

这个模块提供了用户活跃度监控功能，用于实时跟踪系统中的活跃用户数量。
"""

from flask import current_app, g, request, session
import threading
import time
from .monitoring import update_active_users
from .models.base import db
from .models.user import UserOps
import logging
from datetime import datetime, timedelta

# 活跃用户缓存
_active_users_cache = {
    'logged_in': 0,
    'last_update': 0
}

# 缓存更新锁
_cache_lock = threading.Lock()

# 更新周期 (秒)
UPDATE_INTERVAL = 60

# 追踪活跃请求数的计数器
_active_requests = 0
_requests_lock = threading.Lock()

# 存储最近活跃的用户
_recent_active_users = {}
_recent_active_lock = threading.Lock()

def count_active_users():
    """
    统计系统中的活跃用户数量

    基于最近活跃的用户统计
    """
    current_time = time.time()

    with _cache_lock:
        # 如果距离上次更新时间不足UPDATE_INTERVAL秒，直接返回缓存值
        if current_time - _active_users_cache['last_update'] < UPDATE_INTERVAL:
            return _active_users_cache

        try:
            # 清理过期的活跃用户记录
            with _recent_active_lock:
                now = datetime.now()
                expired_users = [
                    user_id for user_id, last_active in _recent_active_users.items()
                    if now - last_active > timedelta(minutes=5)
                ]
                for user_id in expired_users:
                    del _recent_active_users[user_id]

                # 统计活跃用户
                logged_in_count = len(_recent_active_users)

            # 更新缓存
            _active_users_cache['logged_in'] = logged_in_count
            _active_users_cache['last_update'] = current_time

            # 更新指标
            update_active_users(logged_in_count, 'logged_in')

            return _active_users_cache
        except Exception as e:
            if current_app:
                current_app.logger.error(f"统计活跃用户出错: {str(e)}")
            return _active_users_cache

# 定期更新线程
_update_thread = None
_running = False

def _update_loop():
    """后台定期更新活跃用户统计的线程函数"""
    global _running
    while _running:
        try:
            with current_app.app_context():
                count_active_users()
        except Exception as e:
            if current_app:
                current_app.logger.error(f"活跃用户更新线程出错: {str(e)}")
        time.sleep(UPDATE_INTERVAL)

def start_monitoring():
    """启动活跃用户监控"""
    global _update_thread, _running
    if _update_thread is None or not _update_thread.is_alive():
        _running = True
        _update_thread = threading.Thread(target=_update_loop)
        _update_thread.daemon = True
        _update_thread.start()
        if current_app:
            current_app.logger.info("活跃用户监控已启动")

def stop_monitoring():
    """停止活跃用户监控"""
    global _running
    _running = False
    if current_app:
        current_app.logger.info("活跃用户监控已停止")

def init_app(app):
    """初始化用户监控模块"""
    # 在Flask应用上下文中启动监控
    with app.app_context():
        # 启动时立即开始统计
        start_monitoring()

    # 注册路由，用于管理员手动更新和查看活跃用户统计
    from flask import Blueprint, jsonify
    bp = Blueprint('user_monitor', __name__, url_prefix='/user/metrics')

    @bp.route('/active-users/refresh', methods=['POST'])
    def refresh_active_users():
        """手动刷新活跃用户统计"""
        try:
            stats = count_active_users()
            return jsonify({
                "success": True,
                "data": stats
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @bp.route('/active-users', methods=['GET'])
    def get_active_users():
        """获取当前活跃用户统计"""
        try:
            # 如果缓存存在且未过期，直接返回
            if time.time() - _active_users_cache['last_update'] < UPDATE_INTERVAL / 2:
                return jsonify({
                    "success": True,
                    "data": _active_users_cache,
                    "cached": True
                })

            # 否则刷新统计
            stats = count_active_users()
            return jsonify({
                "success": True,
                "data": stats,
                "cached": False
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    # 注册蓝图
    app.register_blueprint(bp)
    app.logger.info("用户活跃度监控初始化成功")

    # 请求计数器，用于区分应用关闭和请求结束
    @app.before_request
    def increment_request_counter():
        global _active_requests
        with _requests_lock:
            _active_requests += 1

        # 更新用户活跃时间
        if session.get('_user_id'):
            with _recent_active_lock:
                _recent_active_users[session['_user_id']] = datetime.now()

        # 顺便检查监控线程是否活跃
        if not _running or _update_thread is None or not _update_thread.is_alive():
            app.logger.warning("检测到监控线程未运行，正在重新启动...")
            start_monitoring()

    @app.teardown_appcontext
    def decrement_request_counter(exception=None):
        global _active_requests

        # 检查应用是否正在关闭
        if app.config.get('SERVER_SHUTTING_DOWN'):
            app.logger.info("应用正在关闭，停止用户监控...")
            stop_monitoring()
            return

        # 减少活跃请求计数
        with _requests_lock:
            _active_requests -= 1
            # 只记录日志，不做任何停止操作
            if _active_requests < 0:
                _active_requests = 0
                app.logger.warning("活跃请求计数器出现负值，已重置为0")