import functools
import random
import string
import time
import hashlib
from collections import OrderedDict

import jwt
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from zchat.models.base import db
from zchat.models.user import *

bp = Blueprint('auth', __name__, url_prefix='/auth')

login_manager = LoginManager()

def init_app(app):
    login_manager.init_app(app)

def init_verification_code_dict(app):
    # Redis实例已经在app中初始化，无需额外操作
    pass

def generate_secure_code(phone_number, length=6):
    """生成安全的验证码，使用时间和手机号作为种子

    Args:
        phone_number: 手机号
        length: 验证码长度，默认6位

    Returns:
        str: 生成的验证码
    """
    # 使用当前时间戳（精确到毫秒）和手机号作为种子
    current_time_ms = int(time.time() * 1000)
    seed_str = f"{phone_number}:{current_time_ms}:{current_app.config['SECRET_KEY']}"

    # 使用哈希函数生成一个种子值
    seed_hash = hashlib.md5(seed_str.encode()).hexdigest()
    seed = int(seed_hash, 16) % 10000000  # 取模得到一个整数种子

    # 使用种子初始化随机数生成器
    random.seed(seed)

    # 生成指定长度的数字验证码
    verification_code = ''.join(random.choice(string.digits) for _ in range(length))

    # 重置随机数生成器，避免影响其他使用随机数的地方
    random.seed()

    return verification_code

class RedisVerificationCode:
    def __init__(self, redis_client, expiration_time=60, cooldown_time=60):
        self.redis = redis_client
        self.expiration_time = expiration_time
        self.cooldown_time = cooldown_time
        self.prefix = "verification_code:"
        self.timestamp_prefix = "verification_timestamp:"

    def __setitem__(self, key, value):
        full_key = f"{self.prefix}{key}"
        timestamp_key = f"{self.timestamp_prefix}{key}"
        # Store both the code and the timestamp
        pipe = self.redis.pipeline()
        pipe.set(full_key, value, ex=self.expiration_time)
        pipe.set(timestamp_key, time.time(), ex=self.expiration_time)
        pipe.execute()

    def __getitem__(self, key):
        full_key = f"{self.prefix}{key}"
        timestamp_key = f"{self.timestamp_prefix}{key}"

        # Get both the code and timestamp
        code = self.redis.get(full_key)
        timestamp = self.redis.get(timestamp_key)

        if code is None or timestamp is None:
            return None

        return (float(timestamp), code)

    def get(self, key, default=None):
        result = self.__getitem__(key)
        return result if result is not None else default

    def can_resend(self, key):
        """Check if enough time has passed to allow resending a code"""
        timestamp_key = f"{self.timestamp_prefix}{key}"
        timestamp = self.redis.get(timestamp_key)

        if timestamp is None:
            return True

        current_time = time.time()
        return current_time - float(timestamp) > self.cooldown_time

    def __delitem__(self, key):
        full_key = f"{self.prefix}{key}"
        timestamp_key = f"{self.timestamp_prefix}{key}"
        pipe = self.redis.pipeline()
        pipe.delete(full_key)
        pipe.delete(timestamp_key)
        pipe.execute()

@bp.route('/verification_code', methods=['GET'])
def verification_code():
    # TODO check if escape is needed
    phone_number = request.args.get('phone_number', '0')

    if phone_number == '0':
        return { "error": "Invalid Phone Number!" }, 400

    # Get the Redis verification code handler
    vcode_handler = RedisVerificationCode(current_app.redis)

    # Check if we can send a new code (cooldown period)
    if not vcode_handler.can_resend(phone_number):
        return { "error": "Please wait before requesting another code" }, 429

    # 使用增强的安全验证码生成方法
    verification_code = generate_secure_code(phone_number)
    vcode_handler[phone_number] = verification_code

    current_app.logger.debug(f"auth/verification_code returns: phone: {phone_number}, code: {verification_code}")

    return jsonify(
        {
            "code": verification_code,
            "error": "succeed"
        }
    )

class LGUser(UserMixin):
    def __init__(self, user):
        self.user = user

    @property
    def is_active(self):
        if self.user is None:
            return False
        return True

    @property
    def is_authenticated(self):
        if self.user is None:
            return False
        return True

    def get_id(self):
        if self.user is not None:
            return str(self.user.id)
        return None

    def get_id_int(self):
        return self.user.id

@login_manager.user_loader
def user_loader(user_id):
    user_ops = UserOps(session=db.session)
    u = user_ops.get_one(id=int(user_id))
    current_app.logger.debug(f"load user of id: {user_id}, is None: {u is None}")
    return LGUser(u)

@login_manager.unauthorized_handler
def unauthorized_handler():
    current_app.logger.warn(f"unauthorized_handler user id: {current_user.get_id()}")
    return 'Unauthorized', 401

@bp.route('/login', methods=['GET']) # TODO to POST
def login():
    phone_number = request.args.get('phone_number', '0')
    verification_code = request.args.get('verification_code', '0')
    invite_code = request.args.get('invite_code', None)  # 新增：接收邀请码

    if phone_number == '0' or verification_code == '0':
        return { "error": "Invalid Phone Number or Verification Code!" }, 400

    # Get the Redis verification code handler
    vcode_handler = RedisVerificationCode(current_app.redis)

    code_data = vcode_handler.get(phone_number)
    if code_data is None:
        return { "error": "Verification code not found or expired" }, 400

    insert_time, expected_code = code_data
    current_time = time.time()

    # Check if the code has expired
    if current_time - insert_time > vcode_handler.expiration_time:
        # Remove expired code
        del vcode_handler[phone_number]
        return { "error": "Verification code has expired" }, 400

    if verification_code != expected_code:
        return { "error": "Incorrect verification code" }, 400

    # Remove the used verification code
    del vcode_handler[phone_number]

    # 处理邀请者ID
    inviter_id = None
    if invite_code:
        try:
            user = User.query.filter_by(invite_code=invite_code).first()
            if user:
                inviter_id = user.id
                current_app.logger.debug(f"Found inviter with ID {inviter_id} for invite code {invite_code}")
            else:
                current_app.logger.debug(f"No inviter found for invite code {invite_code}")
        except Exception as e:
            current_app.logger.error(f"Error finding inviter for invite code {invite_code}: {str(e)}")

    current_app.logger.debug(f'ready to get or create user, {phone_number}, {inviter_id}')

    user_ops = UserOps(session=db.session)
    user_id = user_ops.get_or_create_user(phone_number=phone_number, invited_by=inviter_id)
    if user_id is None:
        current_app.logger.debug(f'no such user, {phone_number}, {inviter_id}')
        return { "error": "No such user!" }, 400

    u = user_ops.get_one(id=user_id)
    user = LGUser(u)
    succeed = login_user(user)
    current_app.logger.debug(f'log in succeed, {user.get_id_int()}, {succeed}')

    token = jwt.encode({'user_id': user_id}, current_app.config['JWT_SECRET_KEY'])
    return jsonify(
        {
            "error": "login succeed",
            "jwt": token,
            "user_id": user_id,
            "invited_by": inviter_id  # 返回邀请者ID信息
        }
    )

@bp.route('/protected')
@login_required
def protected():
    print(session)
    return 'Logged in as: ' + current_user.get_id()

def admin_required(func):
    @functools.wraps(func)
    def decorated_view(*args, **kwargs):
        user_id=current_user.get_id_int()
        admin_user_ops = AdminUserOps(session=db.session)
        is_admin = admin_user_ops.is_admin(user_id=user_id)
        if not is_admin:
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)

    return decorated_view

@bp.route('/logout', methods=['GET']) # TODO to POST
@login_required
def logout():
    user_id = current_user.get_id_int()
    current_app.logger.debug(f'logging out user id, {user_id}')

    logout_user()

    return jsonify(
        {
            "error": "logout succeed",
            "user_id": user_id
        }
    )

