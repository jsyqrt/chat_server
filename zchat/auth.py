import functools
import random
import string
import time
from collections import OrderedDict

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from zchat.db import db
from zchat.models import *

bp = Blueprint('auth', __name__, url_prefix='/auth')

login_manager = LoginManager()

def init_app(app):
    login_manager.init_app(app)

class ExpiringDict(OrderedDict):
    def __init__(self, expiration_time=60):
        super().__init__()
        self.expiration_time = expiration_time

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
        insert_time, value = super().__getitem__(key)
        return value

def init_verification_code_dict(app):
    # TODO change to thread-safe
    app.vcode_dict = ExpiringDict()

@bp.route('/verification_code', methods=['GET'])
def verification_code():
    # TODO check if escape is needed
    phone_number = request.args.get('phone_number', '0')
    verification_code = ''.join(random.choice(string.digits) for _ in range(6))

    if phone_number == '0':
        return { "error": "Invalid Phone Number!" }, 400

    if current_app.vcode_dict.get(phone_number, None) is not None:
        return { "error": "Retry Later!" }, 400

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
    def is_authenticated(self):
        if self.user is None:
            return False
        return True

    def get_id(self):
        return str(self.user.id)

@login_manager.user_loader
def user_loader(id):
    user_ops = UserOps(session=db.session)
    u = user_ops.get_one(id=int(id))
    return LGUser(u)

@login_manager.unauthorized_handler
def unauthorized_handler():
    return 'Unauthorized', 401

@bp.route('/login', methods=['GET']) # TODO to POST
def login():
    phone_number = request.args.get('phone_number', '0')
    verification_code = request.args.get('verification_code', '0')

    if phone_number == '0' or verification_code == '0':
        return { "error": "Invalid Phone Number or Verification Code!" }, 400

    expected_verification_code = current_app.vcode_dict.get(phone_number, None)
    if expected_verification_code is None:
        return { "error": "Wrong Verification Code, not found!" }, 400

    if verification_code != expected_verification_code[1]:
        return { "error": "Wrong Verification Code, it's wrong!" }, 400

    user_ops = UserOps(session=db.session)
    user_id = user_ops.get_or_create_user(phone_number=phone_number)
    if user_id is None:
        return { "error": "No such user!" }, 400

    u = user_ops.get_one(id=user_id)
    user = LGUser(u)
    login_user(user)

    return jsonify(
        {
            "error": "login succeed",
            "user_id": user_id
        }
    )

@bp.route('/protected')
@login_required
def protected():
    print(session)
    return 'Logged in as: ' + current_user.get_id()

@bp.route('/logout', methods=['GET']) # TODO to POST
def logout():
    user_id = current_user.get_id()
    logout_user()
    return jsonify(
        {
            "error": "logout succeed",
            "user_id": user_id
        }
    )

