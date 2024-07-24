import os
import hashlib

from flask import (
    Blueprint, request, jsonify, current_app, g
)

from werkzeug.utils import secure_filename

from zchat.db import db
from zchat.models import *
from zchat.auth import login_required, current_user, admin_required
from zchat.rand import *
from zchat.meili import find_experts_from_meili_for

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/gen_random', methods=['GET'])
def gen_random():
    count = int(request.args.get('count', '50'))

    user_ops = UserOps(session=db.session)
    expert_ops = ExpertOps(session=db.session)
    newbie_ops = NewbieOps(session=db.session)
    for _ in range(count):

        phone_number=random_phone_number()
        nickname=random_name()
        id = user_ops.get_or_create_user(phone_number=phone_number)
        if id is None:
            current_app.logger.warn("failed tp create user")
            continue

        as_expert = random_bool()
        as_newbie = random_bool()

        succeed = user_ops.update_info(
            id=id,
            nickname=nickname,
            phone_number=phone_number,
            gender=random_gender(),
            edubg=random_edubg(),
            yearofwork=random_yearofwork(),
            signature_text=random_signature(),
            current_as_expert=as_expert,
        )
        if not succeed:
            current_app.logger.warn(f"failed tp update user info {id}")
            continue

        succeed = user_ops.update_avatar(
            id=id,
            avatar_name=random_avatar(os.path.join(current_app.static_folder, 'images')))
        if not succeed:
            current_app.logger.warn(f"failed tp update user avatar {id}")
            continue

        if as_expert:
            company=random_company()

            succeed = expert_ops.register_or_update(
                user_id=id,
                email=random_email(nickname, company),
                company=company,
                title=random_title(),
                profession=random_profession(),
                business=random_business(),
                price=random_price(),
            )
            if not succeed:
                current_app.logger.warn(f"failed tp register as expert {id}")
                continue

        if as_newbie:
            succeed = newbie_ops.register_or_update(
                user_id=id,
                company=random_company(),
                title=random_title(),
                profession=random_profession(),
                business=random_business(),
                jd=random_jd(),
            )
            if not succeed:
                current_app.logger.warn(f"failed tp register as newbie {id}")
                continue
    return {'error': f'Succeed to gen random data for count {count}'}


@bp.route('/me', methods=['GET'])
@login_required
def get_me():
    user_ops = UserOps(session=db.session)
    user = user_ops.get_one(id=current_user.get_id_int())
    if user is not None:
        return user.to_dict()
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

@bp.route('/chatlist', methods=['GET'])
@login_required
def get_chatlist():
    chatwith_ops = ChatWithOps(session=db.session)
    user_ops = UserOps(session=db.session)
    chatlist = chatwith_ops.get_chatlist(current_user.get_id_int())
    return [user_ops.get_one(id=user_id).to_dict() for user_id in chatlist]

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

@bp.route('/update_nickname', methods=['POST'])
@login_required
def update_nickname():
    nickname = request.form['nickname']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_nickname(id=current_user.get_id_int(), nickname=nickname)
    if succeed:
        return {'error': 'Nickname updated successfully!'}
    return {'error': 'Failed to update nickname'}, 400

@bp.route('/update_gender', methods=['POST'])
@login_required
def update_gender():
    gender = request.form['gender']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_gender(id=current_user.get_id_int(), gender=gender)
    if succeed:
        return {'error': 'Gender updated successfully!'}
    return {'error': 'Failed to update gender'}, 400

@bp.route('/update_edubg', methods=['POST'])
@login_required
def update_edubg():
    edubg = request.form['edubg']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_edubg(id=current_user.get_id_int(), edubg=edubg)
    if succeed:
        return {'error': 'EduBg updated successfully!'}
    return {'error': 'Failed to update edubg'}, 400

@bp.route('/update_yearofwork', methods=['POST'])
@login_required
def update_yearofwork():
    yearofwork = request.form['yearofwork']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_yearofwork(id=current_user.get_id_int(), yearofwork=yearofwork)
    if succeed:
        return {'error': 'Yearofwork updated successfully!'}
    return {'error': 'Failed to update yearofwork'}, 400

@bp.route('/update_signature', methods=['POST'])
@login_required
def update_signature():
    signature = request.form['signature']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_signature(id=current_user.get_id_int(), signature=signature)
    return {'error': 'Signature updated successfully!'}

@bp.route('/update_role', methods=['POST'])
@login_required
def update_role():
    as_expert = request.form['current_as_expert']

    user_ops = UserOps(session=db.session)
    succeed = user_ops.update_role(id=current_user.get_id_int(), current_as_expert=as_expert)
    return {'error': 'Role updated successfully!'}

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
        as_expert = request.form['current_as_expert']

        user_ops = UserOps(session=db.session)
        succeed = user_ops.update_info(
            id=current_user.get_id_int(),
            phone_number=phone_number,
            nickname=nickname,
            gender=gender,
            edubg=edubg,
            yearofwork=yearofwork,
            signature_text=signature_text,
            current_as_expert=as_expert,
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
            user_id=current_user.get_id_int(),
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

@bp.route('/mark_expert', methods=['POST'])
@login_required
def mark_expert():
    if request.method == 'POST':
        newbie=current_user.get_id_int()
        expert = request.form['expert']

        mark_ops = MarkExpertOps(session=db.session)
        succeed = mark_ops.add_mark(
            newbie=newbie,
            expert=expert,
        )
        if succeed:
            return { "error": "Add expert mark Succeed!" }, 200
        return { "error": "Failed to add expert mark!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400

@bp.route('/mark_expert', methods=['DELETE'])
@login_required
def unmark_expert():
    if request.method == 'DELETE':
        newbie=current_user.get_id_int()
        expert = request.form['expert']

        mark_ops = MarkExpertOps(session=db.session)
        succeed = mark_ops.remove_mark(
            newbie=newbie,
            expert=expert,
        )
        if succeed:
            return { "error": "Remove expert mark Succeed!" }, 200
        return { "error": "Failed to remove expert mark!" }, 400
    else:
        return { "error": "Invalid Request Method!" }, 400

@bp.route('/as_admin', methods=['GET'])
@login_required
@admin_required
def as_admin():
    user_id=current_user.get_id_int()
    admin_user_ops = AdminUserOps(session=db.session)
    admin_id = admin_user_ops.add_as_admin(
        user_id=user_id
    )

    current_app.logger.info(f"added {id} as admin")
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

@bp.route('/marked_expert', methods=['GET'])
@login_required
def get_marked_experts():
    newbie=current_user.get_id_int()

    user_ops = UserOps(session=db.session)
    mark_ops = MarkExpertOps(session=db.session)
    expert_ops = ExpertOps(session=db.session)

    expert_ids = mark_ops.get_marked_experts(
        newbie=newbie,
    )

    result = []
    for id in expert_ids:
        user = user_ops.get_one(id=id)
        if user is not None:
            expert = expert_ops.get_one(user_id=id)
            if expert is not None:
                data = user.to_dict()
                data.update(expert.to_dict())

                # TODO add those
                data['rating'] = 4.5
                data['served'] = 28
                result.append(data)
            else:
                current_app.logger.warn(f"no expert for id: {id}")
        else:
            current_app.logger.warn(f"no user for id: {id}, but it's an expert")
    return result

@bp.route('/my_experts', methods=['GET'])
@login_required
def get_my_experts():
    user_ops = UserOps(session=db.session)
    newbie_ops = NewbieOps(session=db.session)

    newbie = newbie_ops.get_one(user_id=current_user.get_id_int())
    if newbie is None:
        return []

    experts = find_experts_from_meili_for(current_app, newbie=newbie)
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
            user_id=current_user.get_id_int(),
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
