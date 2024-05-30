import os
import hashlib

from flask import (
    Blueprint, request, jsonify, current_app, g
)

from zchat.db import db
from zchat.models import *
from zchat.auth import login_required

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/get_all', methods=['GET'])
@login_required
def get_all():
    user_ops = UserOps(session=db.session)
    all_users = user_ops.get_all_users()
    return all_users

def get_md5(file):
    md5_hash = hashlib.md5()
    for chunk in iter(lambda: file.read(4096), b""):
        md5_hash.update(chunk)
    return md5_hash.hexdigest()

@bp.route('/update_avatar', methods=['POST'])
@login_required
def update_avatar():
    avatar = request.files['avatar']

    md5_hash = get_md5(avatar)
    filename = f"{md5_hash}.{avatar.filename.split('.')[-1]}"
    avatar.save(os.path.join(current_app.static_folder, 'images', filename))

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_avatar(id=g.user.id, avatar_name=filename)
    return {'error': 'Avatar uploaded successfully!'}

@bp.route('/update_info', methods=['POST'])
@login_required
def update_info():
    if request.method == 'POST':
        phone_number = request.form['phone_number']
        nickname = request.form['nickname']
        gender = request.form['gender']
        edubg = request.form['edubg']
        yearofwork = request.form['yearofwork']
        signature_text = request.form['signature_text']

        user_ops = UserOps(session=db.session)
        succeed = user_ops.update_basic(
            id=g.user.id,
            phone_number=phone_number,
            nickname=nickname,
            gender=gender,
            edubg=edubg,
            yearofwork=yearofwork,
            signature_text=signature_text,
        )
        if succeed:
            return { "error": "Update Succeed!" }, 200
        return { "error": "Failed to update!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400
