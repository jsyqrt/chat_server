import os
import hashlib

from flask import (
    Blueprint, request, jsonify, current_app, g
)

from werkzeug.utils import secure_filename

from zchat.db import db
from zchat.models import *
from zchat.auth import login_required

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/me', methods=['GET'])
@login_required
def get_me():
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=g.user.id)
    if user is not None:
        return user.to_dict()
    return {'error': 'Failed to get user info'}, 400

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

    filename = secure_filename(avatar.filename)
    avatar.save(os.path.join(current_app.static_folder, 'images', filename))

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_avatar(id=g.user.id, avatar_name=filename)
    if succeed:
        return {'error': 'Avatar uploaded successfully!'}
    return {'error': 'Failed to update avatar'}, 400

@bp.route('/update_nickname', methods=['POST'])
@login_required
def update_nickname():
    nickname = request.form['nickname']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_nickname(id=g.user.id, nickname=nickname)
    if succeed:
        return {'error': 'Nickname updated successfully!'}
    return {'error': 'Failed to update nickname'}, 400

@bp.route('/update_gender', methods=['POST'])
@login_required
def update_gender():
    gender = request.form['gender']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_gender(id=g.user.id, gender=gender)
    if succeed:
        return {'error': 'Gender updated successfully!'}
    return {'error': 'Failed to update gender'}, 400

@bp.route('/update_edubg', methods=['POST'])
@login_required
def update_edubg():
    edubg = request.form['edubg']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_edubg(id=g.user.id, edubg=edubg)
    if succeed:
        return {'error': 'EduBg updated successfully!'}
    return {'error': 'Failed to update edubg'}, 400

@bp.route('/update_yearofwork', methods=['POST'])
@login_required
def update_yearofwork():
    yearofwork = request.form['yearofwork']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_yearofwork(id=g.user.id, yearofwork=yearofwork)
    if succeed:
        return {'error': 'Yearofwork updated successfully!'}
    return {'error': 'Failed to update yearofwork'}, 400

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
        price = request.form['price']
        need_verify = request.form['need_verify']
        if need_verify:
            # TODO do email verification
            pass

        expert_ops = ExpertOps(session=db.session)
        succeed = expert_ops.register_or_update(
            user_id=g.user.id,
            email=email,
            company=company,
            title=title,
            profession=profession,
            business=business,
            price=float(price),
        )
        if succeed:
            return { "error": "Register as expert Succeed!" }, 200
        return { "error": "Failed to register as expert!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400

@bp.route('/experts', methods=['GET'])
@login_required
def get_all_experts():
    user_ops = UserOps(session=db.session)
    expert_ops = ExpertOps(session=db.session)
    experts = expert_ops.get_all()
    for expert in experts:
        user_id = expert.get('user_id', 0)
        user = user_ops.get_one(id=user_id)
        if user is not None:
            expert.update(user.to_dict())

            # TODO add those
            expert['rating'] = 4.5
            expert['served'] = 28
        else:
            current_app.logger.warn(f"no user for id: {user_id}, but it's an expert")
            continue
    return experts

@bp.route('/register_newbie', methods=['POST'])
@login_required
def register_newbie():
    if request.method == 'POST':
        company = request.form['company']
        title = request.form['title']
        profession = request.form['profession']
        business = request.form['business']
        jd = request.form['jd']

        newbie_ops = NewbieOps(session=db.session)
        succeed = newbie_ops.register_or_update(
            user_id=g.user.id,
            company=company,
            title=title,
            profession=profession,
            business=business,
            jd=jd,
        )
        if succeed:
            return { "error": "Register as newbie Succeed!" }, 200
        return { "error": "Failed to register as newbie!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400
