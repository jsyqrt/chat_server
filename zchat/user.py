import os
import hashlib
import time
import uuid
import json

from flask import (
    Blueprint, request, jsonify, current_app, g, send_file
)

from werkzeug.utils import secure_filename

from zchat.models.base import db
from zchat.models.user import *
# 避免循环导入
# from zchat.models.roadmap import *
from zchat.auth import login_required, current_user, admin_required
from zchat.nosql import *

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
    # Generate a unique filename to prevent collisions
    unique_filename = f"{uuid.uuid4()}_{filename}"
    save_dir = os.path.join(current_app.instance_path, 'images')
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, unique_filename)
    avatar.save(file_path)

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_avatar(id=current_user.get_id_int(), avatar_name=f'/user/image?filename={unique_filename}')
    if succeed:
        return {'message': 'Avatar uploaded successfully!', 'avatar_name': f'/user/image?filename={unique_filename}'}
    return {'error': 'Failed to update avatar'}, 400

@bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    image = request.files['image']
    filename = secure_filename(image.filename)
    # Generate a unique filename to prevent collisions
    unique_filename = f"{uuid.uuid4()}_{filename}"
    save_dir = os.path.join(current_app.instance_path, 'images')
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, unique_filename)
    image.save(file_path)

    # Return a URL that can be used to access the image
    return {
        'message': 'Image uploaded successfully!',
        'image_url': f'/user/image?filename={unique_filename}'
    }

@bp.route('/image', methods=['GET'])
def get_image():
    filename = request.args.get('filename')
    if not filename:
        return {'error': 'No filename provided'}, 400

    # Ensure the filename is secure to prevent directory traversal attacks
    filename = secure_filename(filename)
    file_path = os.path.join(current_app.instance_path, 'images', filename)

    if not os.path.exists(file_path):
        return {'error': 'Image not found'}, 404

    # Determine the MIME type based on file extension
    mime_type = 'image/jpeg'  # Default
    if filename.lower().endswith('.png'):
        mime_type = 'image/png'
    elif filename.lower().endswith('.gif'):
        mime_type = 'image/gif'
    elif filename.lower().endswith('.webp'):
        mime_type = 'image/webp'

    # Return the image file with the appropriate MIME type
    return send_file(file_path, mimetype=mime_type)

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
    interested_industries = request.form['industries']
    interested_roles = request.form['roles']
    interested_skills = request.form['skills']

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


@bp.route('/sync_favorites', methods=['POST'])
@login_required
def sync_favorites():
    roadmaps = request.form['roadmaps']
    cards = request.form['cards']
    user_id = current_user.get_id_int()

    set_favorites_nosql(current_app, user_id, {
        'roadmaps': roadmaps,
        'cards': cards
    })

    # 按需导入，避免循环导入
    from zchat.models.roadmap import RoadmapInteractionOps
    interaction_ops = RoadmapInteractionOps(db.session)

    favorites = interaction_ops.get_favorites(user_id)

    current_app.logger.debug(f"roadmaps: {roadmaps}")

    roadmaps = json.loads(roadmaps)
    for roadmap_id in favorites:
        if roadmap_id not in roadmaps.keys():
            interaction_ops.un_favorite(roadmap_id, user_id)
            current_app.logger.debug(f"unfavorited roadmap {roadmap_id}")

    for roadmap_id in roadmaps.keys():
        if roadmap_id not in favorites:
            interaction_ops.favorite(roadmap_id, user_id)
            current_app.logger.debug(f"favorited roadmap {roadmap_id}")

    # NOTE: cards are counted as favorites

    return {'error': 'Favorites synced successfully!'}


@bp.route('/favorites', methods=['GET'])
@login_required
def get_favorites():
    user_id = current_user.get_id_int()
    favorites = get_favorites_nosql(current_app, user_id)
    current_app.logger.debug(f"favorites: {favorites}")
    if favorites:
        if isinstance(favorites['favorites'], str):
            try:
                # 尝试将字符串解析为 JSON
                favorites['favorites'] = json.loads(favorites['favorites'])
                current_app.logger.debug(f"favorites: {favorites['favorites']}")
            except json.JSONDecodeError:
                # 如果解析失败，则创建一个空字典
                current_app.logger.error(f"Failed to parse favorites: {favorites['favorites']}")
                favorites['favorites'] = {
                    "roadmaps": {},
                    "cards": {}
                }

        return jsonify(favorites['favorites'])
    else:
        results = {}
        # 按需导入，避免循环导入
        from zchat.models.roadmap import RoadmapOps, RoadmapInteractionOps
        roadmap_ops = RoadmapOps(db.session)
        interaction_ops = RoadmapInteractionOps(db.session)
        favorites = interaction_ops.get_favorites(user_id)
        for roadmap_id in favorites:
            roadmap = roadmap_ops.get_roadmap(roadmap_id=roadmap_id)
            if roadmap:
                roadmap_dict = roadmap.to_dict()
                results[roadmap_id] = roadmap_dict

        return jsonify({
            "roadmaps": json.dumps(results),
            "cards": "",
        }), 200

@bp.route('/file_records', methods=['GET'])
@login_required
def get_file_records():
    user_id = current_user.get_id_int()
    file_records = get_file_records_nosql(current_app, user_id)
    current_app.logger.debug(f"file_records: {file_records}")
    if file_records:
        return jsonify(file_records), 200
    else:
        return jsonify({
            'jd_files': [],
            'resume_files': []
        }), 200

@bp.route('/file_content', methods=['GET'])
@login_required
def get_file_content():
    file_name = request.args.get('file_name')
    user_id = current_user.get_id_int()

    file_records = get_file_records_nosql(current_app, user_id)
    if file_records:
        for file in file_records.get('resume_files', []) + file_records.get('jd_files', []):
            if file['filename'] == file_name:
                file_path = file['path']
                break
    if file_path:
        full_file_path = f"{current_app.instance_path}/{file_path}"
        return send_file(full_file_path, mimetype='text/plain')
    else:
        return jsonify({'error': 'File not found'}), 404
