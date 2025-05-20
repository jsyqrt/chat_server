import functools
import random
import string
import time
import hashlib
import uuid
import os
import socket
import traceback
from collections import OrderedDict
from urllib.parse import quote_plus

import jwt
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
import requests

from zchat.models.base import db
from zchat.models.user import *
from zchat.mail import send_verification_email, send_password_reset_email, generate_verification_token

bp = Blueprint('auth', __name__, url_prefix='/auth')

login_manager = LoginManager()
oauth = OAuth()

def init_app(app):
    login_manager.init_app(app)
    oauth.init_app(app)

    # 准备Google OAuth的client_kwargs
    google_client_kwargs = {
        'scope': 'openid email profile',
        'token_endpoint_auth_method': 'client_secret_post',
        'timeout': 60
    }

    # 配置代理设置，只为Google配置代理
    socks_proxy_url = app.config.get('SOCKS_PROXY')
    http_proxy_url = app.config.get('HTTP_PROXY')
    https_proxy_url = app.config.get('HTTPS_PROXY')

    # 配置SSL证书
    try:
        import certifi
        # 使用certifi的CA证书确保SSL连接安全
        google_client_kwargs['verify'] = certifi.where()
        app.logger.info("Using certifi CA certificates")
    except Exception as e:
        app.logger.warning(f"Failed to configure certifi: {str(e)}")

    if http_proxy_url or https_proxy_url or socks_proxy_url:
        try:
            # 优先使用HTTP/HTTPS代理
            if http_proxy_url or https_proxy_url:
                proxy_url = https_proxy_url or http_proxy_url
                app.logger.info(f"使用HTTP代理: {proxy_url}")

                # 为Google客户端添加代理配置
                google_client_kwargs['proxies'] = {
                    'http': http_proxy_url or proxy_url,
                    'https': https_proxy_url or proxy_url
                }

            elif socks_proxy_url:
                # 如果只有SOCKS代理，则使用SOCKS代理
                app.logger.info(f"使用SOCKS代理: {socks_proxy_url}")

                # 解析代理URL
                proxy_parts = socks_proxy_url.split('://')
                if len(proxy_parts) > 1:
                    proxy_type = proxy_parts[0]  # socks5, http等
                    proxy_addr = proxy_parts[1].split('@')[-1].split(':')[0]
                    proxy_port = int(proxy_parts[1].split('@')[-1].split(':')[1]) if ':' in proxy_parts[1].split('@')[-1] else 1080

                    # 测试代理连接
                    app.logger.info(f"Testing proxy connection to {proxy_addr}:{proxy_port}...")
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        result = sock.connect_ex((proxy_addr, proxy_port))
                        sock.close()

                        if result == 0:
                            app.logger.info(f"Proxy connection test successful")
                        else:
                            app.logger.error(f"Proxy connection test failed with error code {result}")
                    except Exception as e:
                        app.logger.error(f"Proxy connection test failed: {str(e)}")

                # 为Google客户端添加代理配置
                google_client_kwargs['proxies'] = {
                    'http': socks_proxy_url,
                    'https': socks_proxy_url
                }

            # 检查必要的依赖包
            try:
                import socks
                app.logger.info("SOCKS library available")
            except ImportError:
                app.logger.error("Missing SOCKS library. Please install 'PySocks' package.")

            app.logger.info(f"Google OAuth configured with proxies: {google_client_kwargs['proxies']}")
        except Exception as e:
            app.logger.error(f"Failed to configure proxy: {str(e)}")
            # 出错时不使用代理
            if 'proxies' in google_client_kwargs:
                del google_client_kwargs['proxies']
    else:
        app.logger.info("No proxy configured for Google OAuth")

    # 使用直接端点URL而不是依赖元数据自动发现
    app.logger.info("Using explicit endpoint URLs for Google OAuth instead of metadata URL")
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        # 不使用server_metadata_url，改为直接配置所有端点
        # server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        access_token_url='https://oauth2.googleapis.com/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/',
        userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
        jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
        client_kwargs=google_client_kwargs,
    )

    app.logger.info(f"Google OAuth registered with client_id: {app.config.get('GOOGLE_CLIENT_ID')[:5]}...")
    app.logger.info(f"Google OAuth configuration complete")

    # 检查SSL证书
    try:
        import ssl
        import certifi
        app.logger.info(f"Using certifi version: {certifi.__version__}")
        app.logger.info(f"SSL version: {ssl.OPENSSL_VERSION}")
    except Exception as e:
        app.logger.warning(f"Could not get SSL information: {str(e)}")

    # 配置GitHub OAuth
    oauth.register(
        name='github',
        client_id=app.config.get('GITHUB_CLIENT_ID'),
        client_secret=app.config.get('GITHUB_CLIENT_SECRET'),
        access_token_url='https://github.com/login/oauth/access_token',
        access_token_params=None,
        authorize_url='https://github.com/login/oauth/authorize',
        authorize_params=None,
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )

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

class RedisTokenStore:
    """Redis存储验证令牌"""
    def __init__(self, redis_client, expiration_time=3600):  # 默认1小时过期
        self.redis = redis_client
        self.expiration_time = expiration_time
        self.verification_prefix = "email_verification:"
        self.reset_prefix = "password_reset:"
        self.refresh_prefix = "jwt_refresh:"

    def store_verification_token(self, user_id, token):
        """存储邮箱验证令牌"""
        key = f"{self.verification_prefix}{user_id}"
        self.redis.set(key, token, ex=self.expiration_time)

    def verify_token(self, user_id, token):
        """验证邮箱验证令牌"""
        key = f"{self.verification_prefix}{user_id}"
        stored_token = self.redis.get(key)
        if stored_token:
            # 如果存储的是字节类型，需要解码
            if isinstance(stored_token, bytes):
                stored_token = stored_token.decode('utf-8')
            if stored_token == token:
                self.redis.delete(key)  # 验证成功后删除令牌
                return True
        return False

    def store_reset_token(self, email, token):
        """存储密码重置令牌"""
        key = f"{self.reset_prefix}{token}"
        self.redis.set(key, email, ex=self.expiration_time)

    def verify_reset_token(self, token):
        """验证密码重置令牌，返回对应的邮箱"""
        key = f"{self.reset_prefix}{token}"
        email = self.redis.get(key)
        if email:
            # 如果存储的是字节类型，需要解码
            if isinstance(email, bytes):
                email = email.decode('utf-8')
            # 注意：这里不删除令牌，等到密码重置成功后再删除
            return email
        return None

    def invalidate_reset_token(self, token):
        """使重置令牌失效"""
        key = f"{self.reset_prefix}{token}"
        self.redis.delete(key)

    def store_refresh_token(self, user_id, token, expiration_time=604800):  # 默认7天过期
        """存储JWT刷新令牌"""
        key = f"{self.refresh_prefix}{token}"
        self.redis.set(key, str(user_id), ex=expiration_time)

    def verify_refresh_token(self, token):
        """验证刷新令牌，返回用户ID"""
        key = f"{self.refresh_prefix}{token}"
        user_id = self.redis.get(key)
        if user_id:
            return int(user_id)
        return None

    def invalidate_refresh_token(self, token):
        """使刷新令牌失效"""
        key = f"{self.refresh_prefix}{token}"
        self.redis.delete(key)

class RedisStateStore:
    """Redis存储OAuth状态参数"""
    def __init__(self, redis_client, expiration_time=600):  # 默认10分钟过期
        self.redis = redis_client
        self.expiration_time = expiration_time
        self.prefix = "oauth_state:"

    def store_state(self, state, callback_scheme):
        """存储状态参数和回调scheme"""
        key = f"{self.prefix}{state}"
        self.redis.set(key, callback_scheme, ex=self.expiration_time)

    def verify_state(self, state):
        """验证状态参数并返回关联的回调scheme"""
        key = f"{self.prefix}{state}"
        callback_scheme = self.redis.get(key)
        if callback_scheme:
            if isinstance(callback_scheme, bytes):
                callback_scheme = callback_scheme.decode('utf-8')
            # 验证成功后删除状态参数
            self.redis.delete(key)
            return callback_scheme
        return None

@bp.route('/verification_code', methods=['POST'])
def verification_code():
    # 修改为POST方法
    data = request.json if request.is_json else request.form
    phone_number = data.get('phone_number', '0')

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

@bp.route('/login', methods=['POST'])
def login():
    data = request.json if request.is_json else request.form
    phone_number = data.get('phone_number', '0')
    verification_code = data.get('verification_code', '0')
    invite_code = data.get('invite_code', None)  # 新增：接收邀请码

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

    # 生成访问令牌和刷新令牌
    access_token = generate_jwt_token(user_id)
    refresh_token = generate_refresh_token(user_id)

    return jsonify(
        {
            "error": "login succeed",
            "jwt": access_token,
            "refresh_token": refresh_token,
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

@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = current_user.get_id_int()
    current_app.logger.debug(f'logging out user id, {user_id}')

    # 从请求中获取刷新令牌（如果有）
    data = request.json if request.is_json else request.form
    refresh_token = data.get('refresh_token')

    # 使刷新令牌失效
    if refresh_token:
        token_store = RedisTokenStore(current_app.redis)
        token_store.invalidate_refresh_token(refresh_token)

    logout_user()

    return jsonify(
        {
            "error": "logout succeed",
            "user_id": user_id
        }
    )

@bp.route('/register', methods=['POST'])
def register():
    """邮箱密码注册"""
    data = request.json if request.is_json else request.form
    email = data.get('email')
    password = data.get('password')
    invite_code = data.get('invite_code')

    if not email or not password:
        return {"error": "Invalid Email or Password!"}, 400

    # 检查邮箱格式
    if '@' not in email:
        return {"error": "Invalid Email!"}, 400

    # 检查密码强度
    if len(password) < 8:
        return {"error": "Password must be at least 8 characters long!"}, 400

    # 处理邀请者ID
    inviter_id = None
    if invite_code:
        try:
            user = User.query.filter_by(invite_code=invite_code).first()
            if user:
                inviter_id = user.id
        except Exception as e:
            current_app.logger.error(f"Error finding inviter for invite code {invite_code}: {str(e)}")

    # 检查邮箱是否已注册
    user_ops = UserOps(session=db.session)
    existing_user = user_ops.get_user_by_email(email)
    if existing_user:
        return {"error": "This email has been registered!"}, 400

    # 创建用户
    user_id = user_ops.get_or_create_user(email=email, password=password, invited_by=inviter_id)
    if not user_id:
        return {"error": "Registration failed!"}, 500

    # 生成验证令牌并发送验证邮件
    token = generate_verification_token()
    token_store = RedisTokenStore(current_app.redis)
    token_store.store_verification_token(user_id, token)

    # 发送验证邮件
    try:
        send_verification_email(user_id, email, token)
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {str(e)}")
        return {"error": "Failed to send verification email, but the account has been created!"}, 201

    # 返回成功信息
    return {
        "error": "register succeed",
        "message": "Registration succeed, please check the verification email!",
        "user_id": user_id
    }, 200

@bp.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    """验证邮箱"""
    if request.method == 'GET':
        # 兼容旧版，从URL参数获取
        user_id = request.args.get('user_id')
        token = request.args.get('token')
    else:
        # 新版使用POST
        data = request.json if request.is_json else request.form
        user_id = data.get('user_id')
        token = data.get('token')

    if not user_id or not token:
        return render_template('customer_service/error.html',
                            title='无效的请求',
                            message='缺少必要的参数，请确保使用正确的验证链接。')

    # 验证令牌
    token_store = RedisTokenStore(current_app.redis)
    if not token_store.verify_token(user_id, token):
        return render_template('customer_service/error.html',
                            title='链接已失效',
                            message='验证链接已过期或无效，请重新申请验证邮件。')

    # 更新用户邮箱验证状态
    user_ops = UserOps(session=db.session)
    if not user_ops.verify_email(user_id):
        return render_template('customer_service/error.html',
                            title='验证失败',
                            message='邮箱验证失败，请稍后重试或联系客服。')

    # 返回HTML页面
    return render_template('customer_service/email_verified.html')

@bp.route('/email_login', methods=['POST'])
def email_login():
    """邮箱密码登录"""
    data = request.json if request.is_json else request.form
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return {"error": "Please provide email and password!"}, 400

    # 根据邮箱查询用户
    user_ops = UserOps(session=db.session)
    user = user_ops.get_user_by_email(email)

    if not user or not user.check_password(password):
        return {"error": "Invalid email or password!"}, 401

    # 检查邮箱是否已验证
    if not user.email_verified:
        return {"error": "Email not verified, please verify your email first!"}, 403

    # 登录用户
    lg_user = LGUser(user)
    login_user(lg_user)

    # 生成访问令牌和刷新令牌
    access_token = generate_jwt_token(user.id)
    refresh_token = generate_refresh_token(user.id)

    return jsonify({
        "error": "login succeed",
        "jwt": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id
    })

@bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    """忘记密码，发送重置邮件"""
    data = request.json if request.is_json else request.form
    email = data.get('email')

    if not email:
        return {"error": "Please provide email!"}, 400

    # 查询用户
    user_ops = UserOps(session=db.session)
    user = user_ops.get_user_by_email(email)

    if not user:
        # 出于安全考虑，即使邮箱不存在也返回成功
        return {"message": "If the email has been registered, the password reset email has been sent!"}, 200

    # 生成重置令牌
    token = generate_verification_token()
    token_store = RedisTokenStore(current_app.redis)
    token_store.store_reset_token(email, token)

    # 发送重置邮件
    try:
        send_password_reset_email(email, token)
    except Exception as e:
        current_app.logger.error(f"Failed to send password reset email: {str(e)}")
        return {"error": "Failed to send password reset email!"}, 500

    return {"message": "The password reset email has been sent, please check it!"}

@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """重置密码"""
    if request.method == 'GET':
        # 显示重置密码表单
        token = request.args.get('token')
        if not token:
            return render_template('customer_service/error.html',
                                title='无效的请求',
                                message='缺少必要的参数，请确保使用正确的重置密码链接。')

        # 验证令牌是否有效
        token_store = RedisTokenStore(current_app.redis)
        email = token_store.verify_reset_token(token)
        if not email:
            return render_template('customer_service/error.html',
                                title='链接已失效',
                                message='重置密码链接已过期或无效，请重新申请重置密码。')

        # 返回重置密码表单页面，同时传递token
        return render_template('customer_service/reset_password.html', token=token)

    elif request.method == 'POST':
        # 处理重置密码表单提交
        data = request.json if request.is_json else request.form
        token = data.get('token')
        new_password = data.get('new_password')

        if not token or not new_password:
            return render_template('customer_service/error.html',
                                title='无效的请求',
                                message='请提供所有必要的信息。')

        if len(new_password) < 8:
            return render_template('customer_service/error.html',
                                title='密码不符合要求',
                                message='密码长度必须至少为8个字符。')

        # 验证令牌
        token_store = RedisTokenStore(current_app.redis)
        email = token_store.verify_reset_token(token)

        if not email:
            return render_template('customer_service/error.html',
                                title='链接已失效',
                                message='重置密码链接已过期或无效，请重新申请重置密码。')

        # 更新密码
        user_ops = UserOps(session=db.session)
        user = user_ops.get_user_by_email(email)

        if not user:
            return render_template('customer_service/error.html',
                                title='用户不存在',
                                message='找不到对应的用户账号，请确认您的邮箱地址。')

        try:
            user.set_password(new_password)
            db.session.commit()

            # 密码更新成功后，使令牌失效
            token_store.invalidate_reset_token(token)

            # 重定向到成功页面
            return redirect(url_for('auth.reset_password_success'))
        except Exception as e:
            current_app.logger.error(f"Failed to reset password: {str(e)}")
            db.session.rollback()
            return render_template('customer_service/error.html',
                                title='重置失败',
                                message='重置密码时发生错误，请稍后重试。')

@bp.route('/reset_password_success')
def reset_password_success():
    """重置密码成功页面"""
    return render_template('customer_service/reset_password_success.html')

def generate_jwt_token(user_id, expiration=3600):
    """生成JWT访问令牌"""
    payload = {
        'user_id': user_id,
        'exp': time.time() + expiration,
        'iat': time.time()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'])

def generate_refresh_token(user_id):
    """生成刷新令牌并存储到Redis"""
    token = str(uuid.uuid4())
    token_store = RedisTokenStore(current_app.redis)
    token_store.store_refresh_token(user_id, token)
    return token

@bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    """使用刷新令牌获取新的访问令牌"""
    data = request.json if request.is_json else request.form
    refresh_token = data.get('refresh_token')

    if not refresh_token:
        return {"error": "Missing refresh token!"}, 400

    # 验证刷新令牌
    token_store = RedisTokenStore(current_app.redis)
    user_id = token_store.verify_refresh_token(refresh_token)

    if not user_id:
        return {"error": "Invalid refresh token or expired!"}, 401

    # 生成新的访问令牌
    access_token = generate_jwt_token(user_id)

    return jsonify({
        "error": "refresh succeed",
        "jwt": access_token,
        "user_id": user_id
    })

@bp.route('/google_login')
def google_login():
    """Google OAuth登录"""
    # 获取状态参数和回调scheme
    state = request.args.get('state')
    callback_scheme = request.args.get('callback_scheme')

    # 如果没有提供state参数，生成一个随机的
    if not state:
        state = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))

    # 存储状态参数和回调scheme
    if callback_scheme:
        state_store = RedisStateStore(current_app.redis)
        state_store.store_state(state, callback_scheme)

    # 构建完整回调URL
    redirect_uri = url_for('auth.google_callback', _external=True)
    current_app.logger.info(f"Google OAuth redirect URI: {redirect_uri}")

    # 设置会话参数，确保不在iframe中加载
    session['oauth_redirect_uri'] = redirect_uri

    try:
        # 添加额外参数以避免iframe问题
        current_app.logger.info("Starting Google authorization redirect")
        return oauth.google.authorize_redirect(
            redirect_uri,
            state=state,
            nonce=hashlib.sha256(os.urandom(32)).hexdigest(),
            prompt='select_account'
        )
    except Exception as e:
        current_app.logger.error(f"Google login error: {e}")
        current_app.logger.error(traceback.format_exc())
        return {"error": f"Google login failed: {str(e)}"}, 500

@bp.route('/google_callback')
def google_callback():
    """Google OAuth回调"""
    # 获取状态参数
    state = request.args.get('state')
    error = request.args.get('error')
    callback_scheme = None

    current_app.logger.info(f"Google callback received, state: {state}, error: {error}")

    # 处理错误情况
    if error:
        error_msg = f"Google authentication error: {error}"
        current_app.logger.error(error_msg)
        return render_template('customer_service/error.html',
                              title='Google登录失败',
                              message=error_msg)

    # 验证状态参数
    if state:
        state_store = RedisStateStore(current_app.redis)
        callback_scheme = state_store.verify_state(state)
        if not callback_scheme:
            error_msg = "Invalid state parameter, possible CSRF attack"
            current_app.logger.error(error_msg)
            return {"error": error_msg}, 400

    # 处理OAuth回调
    try:
        # 获取访问令牌
        current_app.logger.info("Attempting to get access token from Google...")
        token = oauth.google.authorize_access_token()
        token_keys = list(token.keys())
        current_app.logger.info(f"Received token with keys: {token_keys}")

        # 获取用户信息 - 使用标准的OpenID Connect endpoint
        current_app.logger.info("Getting user info from Google...")

        # 从token中获取access_token
        access_token = token.get('access_token')
        if not access_token:
            current_app.logger.error("No access_token in response")
            raise ValueError("Missing access token")

        # 使用标准的userinfo端点
        userinfo_endpoint = 'https://openidconnect.googleapis.com/v1/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}

        # 创建会话并设置代理（如果配置了）
        session = requests.Session()
        if hasattr(oauth.google, '_client_kwargs') and 'proxies' in oauth.google._client_kwargs:
            session.proxies.update(oauth.google._client_kwargs['proxies'])
            current_app.logger.info(f"Using proxies for userinfo request: {session.proxies}")

        # 设置SSL验证
        verify = True
        if hasattr(oauth.google, '_client_kwargs') and 'verify' in oauth.google._client_kwargs:
            verify = oauth.google._client_kwargs['verify']

        # 发送请求获取用户信息
        current_app.logger.info(f"Sending request to {userinfo_endpoint}")
        response = session.get(
            userinfo_endpoint,
            headers=headers,
            timeout=60,
            verify=verify
        )
        response.raise_for_status()
        user_info = response.json()
        current_app.logger.info(f"Received user info with email: {user_info.get('email')}")

        # 验证用户信息
        if not user_info or 'email' not in user_info:
            error_msg = "Google login failed, unable to get user information"
            current_app.logger.error(f"User info missing email: {user_info}")
            if callback_scheme:
                redirect_url = f"{callback_scheme}://oauth_callback?error={quote_plus(error_msg)}&state={state}"
                return redirect(redirect_url)
            return {"error": error_msg}, 400

        email = user_info['email']

        # 获取用户ID - OpenID Connect使用'sub'作为标准的用户ID
        if 'sub' not in user_info:
            current_app.logger.error(f"No 'sub' field in user info: {user_info}")
            error_msg = "Invalid user information from Google"
            if callback_scheme:
                redirect_url = f"{callback_scheme}://oauth_callback?error={quote_plus(error_msg)}&state={state}"
                return redirect(redirect_url)
            return {"error": error_msg}, 400

        oauth_id = user_info['sub']
        current_app.logger.info(f"Processing login for Google user: {email} with ID: {oauth_id}")

        # 查找或创建用户
        user_ops = UserOps(session=db.session)
        user = user_ops.get_user_by_oauth('google', oauth_id)

        if not user:
            user = user_ops.get_user_by_email(email)

            if user:
                # 如果邮箱已存在，关联OAuth信息
                user.set_oauth_info('google', oauth_id)
                db.session.commit()
                current_app.logger.info(f"Linked Google account to existing user: {email}")
            else:
                # 创建新用户
                nickname = user_info.get('name', email.split('@')[0])
                current_app.logger.info(f"Creating new user for Google account: {email}")
                user_id = user_ops.get_or_create_user(
                    email=email,
                    oauth_provider='google',
                    oauth_id=oauth_id
                )
                user = user_ops.get_one(id=user_id)

                if not user:
                    error_msg = "Failed to create user!"
                    current_app.logger.error(f"Failed to create user for {email}")
                    if callback_scheme:
                        redirect_url = f"{callback_scheme}://oauth_callback?error={quote_plus(error_msg)}&state={state}"
                        return redirect(redirect_url)
                    return {"error": error_msg}, 500

                # 设置额外的用户信息
                if 'picture' in user_info and user_info['picture']:
                    user.avatar_name = user_info['picture']

                if nickname:
                    user.nickname = nickname

                # 对于OAuth登录，自动验证邮箱
                user.email_verified = True
                db.session.commit()
                current_app.logger.info(f"Created new user for Google account: {email}, ID: {user.id}")

        # 登录用户
        lg_user = LGUser(user)
        login_user(lg_user)
        current_app.logger.info(f"Logged in Google user: {email}, ID: {user.id}")

        # 生成访问令牌和刷新令牌
        access_token = generate_jwt_token(user.id)
        refresh_token = generate_refresh_token(user.id)
        current_app.logger.info(f"Generated tokens for user: {user.id}")

        # 如果有回调scheme，重定向到应用
        if callback_scheme:
            redirect_url = f"{callback_scheme}://oauth_callback?token={access_token}&refresh_token={refresh_token}&provider=google&state={state}"
            current_app.logger.info(f"Redirecting to app: {callback_scheme}")
            return redirect(redirect_url)

        # 否则返回JSON响应
        return jsonify({
            "success": True,
            "jwt": access_token,
            "refresh_token": refresh_token,
            "user_id": user.id
        })
    except Exception as e:
        current_app.logger.error(f"Google OAuth callback error: {str(e)}")
        current_app.logger.error(traceback.format_exc())

        error_msg = f"Authentication failed: {str(e)}"
        if callback_scheme:
            redirect_url = f"{callback_scheme}://oauth_callback?error={quote_plus(error_msg)}&state={state}"
            return redirect(redirect_url)
        return {"error": error_msg}, 500

@bp.route('/github_login')
def github_login():
    """GitHub OAuth登录"""
    # 获取状态参数和回调scheme
    state = request.args.get('state')
    callback_scheme = request.args.get('callback_scheme')

    # 如果没有提供state参数，生成一个随机的
    if not state:
        state = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))

    # 存储状态参数和回调scheme
    if callback_scheme:
        state_store = RedisStateStore(current_app.redis)
        state_store.store_state(state, callback_scheme)

    # 生成重定向URI，添加状态参数
    redirect_uri = url_for('auth.github_callback', _external=True)
    return oauth.github.authorize_redirect(redirect_uri, state=state)

@bp.route('/github_callback')
def github_callback():
    """GitHub OAuth回调"""
    # 获取状态参数
    state = request.args.get('state')
    callback_scheme = None

    # 验证状态参数
    if state:
        state_store = RedisStateStore(current_app.redis)
        callback_scheme = state_store.verify_state(state)

    # 处理OAuth回调
    try:
        token = oauth.github.authorize_access_token()
        resp = oauth.github.get('user', token=token)
        user_info = resp.json()

        if not user_info or 'id' not in user_info:
            error_msg = "GitHub login failed, unable to get user information!"
            if callback_scheme:
                redirect_url = f"{callback_scheme}://oauth_callback?error={error_msg}&state={state}"
                return redirect(redirect_url)
            return {"error": error_msg}, 400

        oauth_id = str(user_info['id'])

        # GitHub不会直接提供公开邮箱，需要额外请求邮箱信息
        email = None
        try:
            emails_resp = oauth.github.get('user/emails', token=token)
            emails_data = emails_resp.json()
            # 查找主要且已验证的邮箱
            for email_data in emails_data:
                if email_data.get('primary', False) and email_data.get('verified', False):
                    email = email_data.get('email')
                    break
            # 如果没有找到主要邮箱，使用第一个已验证的邮箱
            if not email:
                for email_data in emails_data:
                    if email_data.get('verified', False):
                        email = email_data.get('email')
                        break
        except Exception as e:
            current_app.logger.error(f"Failed to get GitHub emails: {str(e)}")

        if not email:
            error_msg = "GitHub login failed, unable to get valid email!"
            if callback_scheme:
                redirect_url = f"{callback_scheme}://oauth_callback?error={error_msg}&state={state}"
                return redirect(redirect_url)
            return {"error": error_msg}, 400

        # 查找或创建用户
        user_ops = UserOps(session=db.session)
        user = user_ops.get_user_by_oauth('github', oauth_id)

        if not user:
            user = user_ops.get_user_by_email(email)

            if user:
                # 如果邮箱已存在，关联OAuth信息
                user.set_oauth_info('github', oauth_id)
                db.session.commit()
            else:
                # 创建新用户
                nickname = user_info.get('name') or user_info.get('login', '用户')
                user_id = user_ops.get_or_create_user(
                    email=email,
                    oauth_provider='github',
                    oauth_id=oauth_id
                )
                user = user_ops.get_one(id=user_id)

                if not user:
                    error_msg = "Failed to create user!"
                    if callback_scheme:
                        redirect_url = f"{callback_scheme}://oauth_callback?error={error_msg}&state={state}"
                        return redirect(redirect_url)
                    return {"error": error_msg}, 500

                # 对于OAuth登录，自动验证邮箱
                user.email_verified = True
                db.session.commit()

        # 登录用户
        lg_user = LGUser(user)
        login_user(lg_user)

        # 生成访问令牌和刷新令牌
        access_token = generate_jwt_token(user.id)
        refresh_token = generate_refresh_token(user.id)

        # 如果有回调scheme，重定向到应用
        if callback_scheme:
            redirect_url = f"{callback_scheme}://oauth_callback?token={access_token}&refresh_token={refresh_token}&provider=github&state={state}"
            return redirect(redirect_url)

        # 否则返回JSON响应
        return jsonify({
            "error": "login succeed",
            "jwt": access_token,
            "refresh_token": refresh_token,
            "user_id": user.id
        })
    except Exception as e:
        current_app.logger.error(f"GitHub OAuth callback error: {str(e)}")
        error_msg = "Authentication failed"
        if callback_scheme:
            redirect_url = f"{callback_scheme}://oauth_callback?error={error_msg}&state={state}"
            return redirect(redirect_url)
        return {"error": error_msg}, 500

# 用户管理接口
@bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    data = request.json if request.is_json else request.form
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return {"error": "Please provide current password and new password!"}, 400

    if len(new_password) < 8:
        return {"error": "New password must be at least 8 characters long!"}, 400

    # 获取当前用户
    user_id = current_user.get_id_int()
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=user_id)

    # 验证当前密码
    if not user.check_password(current_password):
        return {"error": "Current password is incorrect!"}, 401

    # 更新密码
    user.set_password(new_password)
    db.session.commit()

    return {"message": "Password updated successfully!"}

@bp.route('/bind_phone', methods=['POST'])
@login_required
def bind_phone():
    """绑定手机号"""
    data = request.json if request.is_json else request.form
    phone_number = data.get('phone_number')
    verification_code = data.get('verification_code')

    if not phone_number or not verification_code:
        return {"error": "Please provide phone number and verification code!"}, 400

    # 验证验证码
    vcode_handler = RedisVerificationCode(current_app.redis)
    code_data = vcode_handler.get(phone_number)

    if code_data is None:
        return {"error": "Verification code does not exist or has expired!"}, 400

    insert_time, expected_code = code_data
    current_time = time.time()

    if current_time - insert_time > vcode_handler.expiration_time:
        del vcode_handler[phone_number]
        return {"error": "Verification code has expired!"}, 400

    if verification_code != expected_code:
        return {"error": "Verification code is incorrect!"}, 400

    # 验证码正确，删除
    del vcode_handler[phone_number]

    # 检查手机号是否已被其他用户绑定
    user_ops = UserOps(session=db.session)
    existing_user = user_ops.get_user_by_phone(phone_number)

    if existing_user and existing_user.id != current_user.get_id_int():
        return {"error": "This phone number has been bound to another account!"}, 400

    # 绑定手机号
    user_id = current_user.get_id_int()
    success = user_ops.update_phone(user_id, phone_number)

    if success:
        return {"message": "Phone number bound successfully!"}
    else:
        return {"error": "Failed to bind phone number!"}, 500

@bp.route('/unbind_phone', methods=['POST'])
@login_required
def unbind_phone():
    """解绑手机号"""
    # 获取当前用户
    user_id = current_user.get_id_int()
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=user_id)

    # 检查用户是否已绑定手机号
    if not user.phone_number:
        return {"error": "Current account is not bound to a phone number!"}, 400

    # 检查是否有邮箱，确保至少保留一种登录方式
    if not user.email:
        return {"error": "Unable to unbind phone number, account must retain at least one login method!"}, 400

    # 解绑手机号
    success = user_ops.update_phone(user_id, None)

    if success:
        return {"message": "Phone number unbound successfully!"}
    else:
        return {"error": "Failed to unbind phone number!"}, 500

@bp.route('/bind_email', methods=['POST'])
@login_required
def bind_email():
    """绑定邮箱"""
    data = request.json if request.is_json else request.form
    email = data.get('email')

    if not email:
        return {"error": "Please provide email!"}, 400

    # 检查邮箱格式
    if '@' not in email:
        return {"error": "Invalid email format!"}, 400

    # 检查邮箱是否已被其他用户绑定
    user_ops = UserOps(session=db.session)
    existing_user = user_ops.get_user_by_email(email)

    if existing_user and existing_user.id != current_user.get_id_int():
        return {"error": "This email has been bound to another account!"}, 400

    # 获取当前用户
    user_id = current_user.get_id_int()
    user = user_ops.get_one(id=user_id)

    # 如果已经绑定了相同的邮箱
    if user.email == email and user.email_verified:
        return {"message": "Current email is already bound and verified!"}

    # 更新邮箱
    success = user_ops.update_email(user_id, email, False)  # 新绑定的邮箱需要验证

    if not success:
        return {"error": "Failed to bind email!"}, 500

    # 生成验证令牌并发送验证邮件
    token = generate_verification_token()
    token_store = RedisTokenStore(current_app.redis)
    token_store.store_verification_token(user_id, token)

    # 发送验证邮件
    try:
        send_verification_email(user_id, email, token)
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {str(e)}")
        return {"error": "Email is already bound, but failed to send verification email!"}, 201

    return {"message": "Email bound successfully, please check the verification email!"}

@bp.route('/unbind_email', methods=['POST'])
@login_required
def unbind_email():
    """解绑邮箱"""
    # 获取当前用户
    user_id = current_user.get_id_int()
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=user_id)

    # 检查用户是否已绑定邮箱
    if not user.email:
        return {"error": "Current account is not bound to an email!"}, 400

    # 检查是否有手机号，确保至少保留一种登录方式
    if not user.phone_number:
        return {"error": "Unable to unbind email, account must retain at least one login method!"}, 400

    # 解绑邮箱
    success = user_ops.update_email(user_id, None, False)

    if success:
        return {"message": "Email unbound successfully!"}
    else:
        return {"error": "Failed to unbind email!"}, 500

@bp.route('/validate_oauth_token', methods=['POST'])
def validate_oauth_token():
    """验证OAuth回调返回的令牌"""
    data = request.json if request.is_json else request.form
    token = data.get('token')
    provider = data.get('provider')

    if not token:
        return jsonify({
            "success": False,
            "error": "Missing token"
        }), 400

    # 验证令牌
    try:
        # 解码JWT令牌获取用户ID
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user_id = payload.get('user_id')

        if not user_id:
            return jsonify({
                "success": False,
                "error": "Invalid token"
            }), 401

        # 获取用户信息
        user_ops = UserOps(session=db.session)
        user = user_ops.get_one(id=user_id)

        if not user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 404

        # 返回用户信息
        return jsonify({
            "success": True,
            "jwt": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.nickname,
                "avatar_url": user.avatar_name
            }
        })
    except jwt.ExpiredSignatureError:
        return jsonify({
            "success": False,
            "error": "Token expired"
        }), 401
    except jwt.InvalidTokenError:
        return jsonify({
            "success": False,
            "error": "Invalid token"
        }), 401
    except Exception as e:
        current_app.logger.error(f"Token validation error: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Authentication failed"
        }), 500

@bp.route('/user', methods=['GET'])
@login_required
def get_user_info():
    """获取当前用户信息"""
    user_id = current_user.get_id_int()
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    # 获取用户的认证提供商列表
    auth_providers = []
    if user.oauth_provider == 'google' and user.oauth_id:
        auth_providers.append("google")
    if user.oauth_provider == 'github' and user.oauth_id:
        auth_providers.append("github")
    if user.email and user.password_hash:
        auth_providers.append("email")
    if user.phone_number:
        auth_providers.append("phone")

    return jsonify({
        "user_id": user.id,
        "email": user.email,
        "name": user.nickname,
        "avatar_url": user.avatar_name,
        "auth_providers": auth_providers
    })

