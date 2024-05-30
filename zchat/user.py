import os
import hashlib

from flask import (
    Blueprint, request, jsonify, current_app, g
)

from zchat.db import db
from zchat.models import *
from zchat.auth import login_required

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/all', methods=['GET'])
@login_required
def get_all():
    user_ops = UserOps(session=db.session)
    all_users = user_ops.get_all()
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

@bp.route('/update_nickname', methods=['POST'])
@login_required
def update_nickname():
    nickname = request.form['nickname']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_nickname(id=g.user.id, nickname=nickname)
    return {'error': 'Nickname updated successfully!'}

@bp.route('/update_signature', methods=['POST'])
@login_required
def update_signature():
    signature = request.form['signature']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_signature(id=g.user.id, signature=signature)
    return {'error': 'Signature updated successfully!'}

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
        succeed = user_ops.update_info(
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

@bp.route('/register_expert', methods=['POST'])
@login_required
def register_expert():
    if request.method == 'POST':
        email = request.form['email']
        company = request.form['company']
        title = request.form['title']
        profession = request.form['profession']
        business = request.form['business']

        expert_ops = ExpertOps(session=db.session)
        succeed = expert_ops.register_or_update(
            user_id=g.user.id,
            email=email,
            company=company,
            title=title,
            profession=profession,
            business=business,
        )
        if succeed:
            return { "error": "Register as expert Succeed!" }, 200
        return { "error": "Failed to register as expert!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400
