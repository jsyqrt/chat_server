import time
import threading
import schedule
import logging
from datetime import datetime

from flask import current_app
from zchat.db import db
from zchat.models.user import UserOps
from zchat.models.points import PointsOps
from zchat.models.subscription import AccountType

class Scheduler:
    """
    定时任务调度器，用于定期执行系统维护任务，如订阅过期检查、积分过期检查等
    """

    def __init__(self, app=None):
        self.app = app
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        self.logger = logging.getLogger('zchat.scheduler')

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        初始化应用
        """
        self.app = app

        # 添加应用关闭时的清理
        app.teardown_appcontext(self.teardown)

        # 在应用启动时启动调度器
        with app.app_context():
            self.start()

    def teardown(self, exception):
        """
        应用关闭时的清理工作
        """
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop()

    def start(self):
        """
        启动调度器
        """
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.logger.warning('Scheduler already running')
            return

        # 设置定时任务
        schedule.clear()

        # 每小时检查一次订阅过期
        schedule.every().hour.do(self.check_subscription_expiry)

        # 每天凌晨检查积分过期
        schedule.every().day.at("00:05").do(self.check_points_expiry)

        # 启动线程运行调度器
        self.stop_event.clear()
        self.scheduler_thread = threading.Thread(target=self.run, daemon=True)
        self.scheduler_thread.start()

        self.logger.info('Scheduler started')

    def stop(self):
        """
        停止调度器
        """
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_event.set()
            self.scheduler_thread.join(timeout=5)
            self.logger.info('Scheduler stopped')

    def run(self):
        """
        运行调度器主循环
        """
        self.logger.info('Scheduler thread started')
        with self.app.app_context():
            while not self.stop_event.is_set():
                schedule.run_pending()
                time.sleep(1)
        self.logger.info('Scheduler thread stopped')

    def check_subscription_expiry(self):
        """
        检查订阅过期
        """
        try:
            self.logger.info('Checking subscription expiry...')

            # 检查所有用户的订阅过期情况
            user_ops = UserOps(db.session)

            # 获取所有用户
            users = user_ops.get_all()
            expired_count = 0

            for user in users:
                try:
                    # 检查并更新用户订阅状态
                    updated = user_ops.check_and_update_subscription_status(user['id'])
                    if updated:
                        expired_count += 1
                except Exception as e:
                    self.logger.error(f"Error checking subscription for user {user['id']}: {str(e)}")

            if expired_count > 0:
                self.logger.info(f'Subscription check complete. Found {expired_count} expired subscriptions.')
        except Exception as e:
            self.logger.error(f'Error in check_subscription_expiry: {str(e)}')

    def check_points_expiry(self):
        """
        检查积分过期
        """
        try:
            self.logger.info('Checking points expiry...')

            # 检查所有过期的积分
            points_ops = PointsOps(db.session)
            success = points_ops.check_and_expire_points()

            if success:
                self.logger.info('Points expiry check complete.')
            else:
                self.logger.warning('Points expiry check failed.')
        except Exception as e:
            self.logger.error(f'Error in check_points_expiry: {str(e)}')


# 全局调度器实例
scheduler = Scheduler()


def init_app(app):
    """
    初始化调度器
    """
    global scheduler
    scheduler.init_app(app)