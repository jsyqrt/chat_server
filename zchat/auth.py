import functools
import random
import string
import time
from collections import OrderedDict

import jwt
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from zchat.db import db
from zchat.models.user import *

bp = Blueprint('auth', __name__, url_prefix='/auth')

login_manager = LoginManager()

def init_app(app):
    login_manager.init_app(app)

def init_verification_code_dict(app):
    # TODO change to thread-safe
    app.vcode_dict = ExpiringDict()

class ExpiringDict(OrderedDict):
    def __init__(self, expiration_time=60, cooldown_time=60):
        super().__init__()
        self.expiration_time = expiration_time
        self.cooldown_time = cooldown_time

    def __setitem__(self, key, value):
        self.remove_expired_items()
        super().__setitem__(key, (time.time(), value))

    def remove_expired_items(self):
        current_time = time.time()
        for key, (insert_time, value) in list(self.items()):
            if current_time - insert_time > self.expiration_time:
                del self[key]

    def __getitem__(self, key):
        self.remove_expired_items()
        if key not in self:
            return None
        insert_time, value = super().__getitem__(key)
        return (insert_time, value)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except:
            return default

    def can_resend(self, key):
        """Check if enough time has passed to allow resending a code"""
        item = self.get(key)
        if item is None:
            return True

        insert_time, _ = item
        current_time = time.time()
        return current_time - insert_time > self.cooldown_time

@bp.route('/verification_code', methods=['GET'])
def verification_code():
    # TODO check if escape is needed
    phone_number = request.args.get('phone_number', '0')
    verification_code = ''.join(random.choice(string.digits) for _ in range(6))

    if phone_number == '0':
        return { "error": "Invalid Phone Number!" }, 400

    # Check if we can send a new code (cooldown period)
    if not current_app.vcode_dict.can_resend(phone_number):
        return { "error": "Please wait before requesting another code" }, 429

    current_app.vcode_dict[phone_number] = verification_code

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

    code_data = current_app.vcode_dict.get(phone_number)
    if code_data is None:
        return { "error": "Verification code not found or expired" }, 400

    insert_time, expected_code = code_data
    current_time = time.time()

    # Check if the code has expired
    if current_time - insert_time > current_app.vcode_dict.expiration_time:
        # Remove expired code
        del current_app.vcode_dict[phone_number]
        return { "error": "Verification code has expired" }, 400

    if verification_code != expected_code:
        return { "error": "Incorrect verification code" }, 400

    # Remove the used verification code
    del current_app.vcode_dict[phone_number]

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

    user_ops = UserOps(session=db.session)
    user_id = user_ops.get_or_create_user(phone_number=phone_number, invited_by=inviter_id)
    if user_id is None:
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
    current_app.logger.debug(f'loging out user id, {user_id}')
    try:
        sid = app.get_user_session(user_id)
        if sid:
            app.socketio.disconnect(sid)

        logout_user()
        current_app.remove_user_session(user_id)

    except Exception as e:
        pass

    return jsonify(
        {
            "error": "logout succeed",
            "user_id": user_id
        }
    )

