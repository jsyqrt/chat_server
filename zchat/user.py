import os
import hashlib

from flask import (
    Blueprint, request, jsonify, current_app, g
)

from werkzeug.utils import secure_filename

from zchat.db import db
from zchat.models.user import *
from zchat.auth import login_required, current_user, admin_required

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/me', methods=['GET'])
@login_required
def get_me():
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=current_user.get_id_int())
    if user is not None:
        user_info = user.to_dict()
        return user_info

    return {'error': 'Failed to get user info'}, 400

@bp.route('/avatar', methods=['GET'])
def get_avatar():
    id = request.args.get('id')

    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=id)
    if user is not None:
        return {
            'id' : id,
            'avatar' : user.to_dict()['avatar'],
        }
    return {'error': 'Failed to get user avatar'}, 400

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
    succeed = user_ops.update_avatar(id=current_user.get_id_int(), avatar_name=filename)
    if succeed:
        return {'error': 'Avatar uploaded successfully!'}
    return {'error': 'Failed to update avatar'}, 400

@bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    image = request.files['image']
    filename = secure_filename(image.filename)
    image.save(os.path.join(current_app.static_folder, 'images', filename))

    return {
        'error': 'Image uploaded successfully!',
        'image_url': url_for('static', filename=f'images/{filename}')
    }

@bp.route('/update_nickname', methods=['POST'])
@login_required
def update_nickname():
    nickname = request.form['nickname']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_nickname(id=current_user.get_id_int(), nickname=nickname)
    if succeed:
        return {'error': 'Nickname updated successfully!'}
    return {'error': 'Failed to update nickname'}, 400

@bp.route('/update_basic_info', methods=['POST'])
@login_required
def update_basic_info():
    gender = request.form['gender']
    edubg = request.form['edubg']
    yearofwork = request.form['yearofwork']

    user_ops = UserOps(session=db.session)
    update_gender_succeed = user_ops.update_gender(id=current_user.get_id_int(), gender=gender)
    update_edubg_succeed = user_ops.update_edubg(id=current_user.get_id_int(), edubg=edubg)
    update_yearofwork_succeed = user_ops.update_yearofwork(id=current_user.get_id_int(), yearofwork=yearofwork)
    if update_gender_succeed and update_edubg_succeed and update_yearofwork_succeed:
        return {'error': 'Basic info updated successfully!'}
    else:
        current_app.logger.warn(
            f"""failed to update basic info for user {current_user.get_id_int()}
            update_gender_succeed: {update_gender_succeed},
            update_edubg_succeed: {update_edubg_succeed},
            update_yearofwork_succeed: {update_yearofwork_succeed}
            """
        )
        return {'error': 'Failed to update basic info'}, 400

@bp.route('/update_signature', methods=['POST'])
@login_required
def update_signature():
    signature = request.form['signature']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_signature(id=current_user.get_id_int(), signature=signature)
    return {'error': 'Signature updated successfully!'}

@bp.route('/update_interested_tags', methods=['POST'])
@login_required
def update_interested_tags():
    interested_industries = request.form['interested_industries']
    interested_roles = request.form['interested_roles']
    interested_skills = request.form['interested_skills']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_interested_tags(
        id=current_user.get_id_int(),
        interested_industries=interested_industries,
        interested_roles=interested_roles,
        interested_skills=interested_skills
    )
    if succeed:
        return {'error': 'Interested tags updated successfully!'}
    return {'error': 'Failed to update interested tags'}, 400

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

        interested_industries = request.form['interested_industries']
        interested_roles = request.form['interested_roles']
        interested_skills = request.form['interested_skills']

        user_ops = UserOps(session=db.session)
        succeed = user_ops.update_info(
            id=current_user.get_id_int(),
            phone_number=phone_number,
            nickname=nickname,
            gender=gender,
            edubg=edubg,
            yearofwork=yearofwork,
            signature_text=signature_text,
            interested_industries=interested_industries,
            interested_roles=interested_roles,
            interested_skills=interested_skills,
        )
        if succeed:
            return { "error": "Update Succeed!" }, 200
        return { "error": "Failed to update!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400

@bp.route('/as_admin', methods=['GET'])
@login_required
@admin_required
def as_admin():
    user_id = int(request.args.get('id'))

    admin_user_ops = AdminUserOps(session=db.session)
    admin_id = admin_user_ops.add_as_admin(
        user_id=user_id
    )

    current_app.logger.info(f"added {user_id} as admin")
    return {'admin_id': admin_id}

@bp.route('/is_admin', methods=['GET'])
@login_required
def is_admin():
    user_id=current_user.get_id_int()
    current_app.logger.debug(f"user id: {user_id}")
    admin_user_ops = AdminUserOps(session=db.session)
    is_admin = admin_user_ops.is_admin(user_id=user_id)
    current_app.logger.debug(f"is admin: {is_admin}")
    return {'is_admin': is_admin}

