import functools
import random
import string
import time
from collections import OrderedDict

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash

from zchat.db import db
from zchat.models import *

bp = Blueprint('auth', __name__, url_prefix='/auth')

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
    session['user_id'] = user_id
    return jsonify(
        {
            "error": "login succeed",
            "user_id": user_id
        }
    )

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    current_app.logger.debug(f"load_logged_in_user {user_id}")

    if user_id is None:
        g.user = None
    else:
        user_ops = UserOps(session=db.session)
        g.user = user_ops.get_one(id=user_id)

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return {'error': 'login required'}, 400

        return view(**kwargs)

    return wrapped_view

@bp.route('/logout', methods=['GET']) # TODO to POST
def logout():
    user_id = session['user_id']
    session.clear()
    return jsonify(
        {
            "error": "logout succeed",
            "user_id": user_id
        }
    )

