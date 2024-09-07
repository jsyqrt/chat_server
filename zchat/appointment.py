import os
import hashlib
from pathlib import Path

from flask import (
    Blueprint, request, jsonify, current_app, g, send_file
)

from werkzeug.utils import secure_filename

from zchat.db import db
from zchat.models import *
from zchat.auth import login_required, current_user, admin_required
from zchat.rand import *

bp = Blueprint('appointment', __name__, url_prefix='/appointment')

def appointment_change_event_notify(app, appointment_dict, other_id):
    sid = app.get_user_session(other_id)
    if sid:
        app.logger.debug(f"sending appointment_update {appointment_dict} to {sid}")
        app.socketio.emit('appointment_update', appointment_dict, to=sid)

@bp.route('/new', methods=['POST'])
@login_required
def new_appointment():
    expert = int(request.form['expert'])
    type = int(request.form['type'])
    newbie = current_user.get_id_int()
    timestamp = float(request.form['timestamp'])

    if expert == 0 or newbie == 0:
        return {'error': f'Invalid expert or newbie setting {expert}, {newbie}'}, 400

    app_ops = AppointmentOps(session=db.session)
    id = app_ops.create_appointment(type=type, expert=expert, newbie=newbie, timestamp=timestamp)
    if id is not None:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, expert)
        return data

    return {'error': 'Failed to create appointment'}, 400

@bp.route('/update_time', methods=['POST'])
@login_required
def update_time():
    id = request.form['id']
    timestamp = float(request.form['timestamp'])
    newbie = current_user.get_id_int()

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.update_timestamp(id=id, newbie_id=newbie, timestamp=timestamp)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    id = request.form['id']
    newbie = current_user.get_id_int()

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.newbie_cancel(id=id, newbie_id=newbie)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/confirm', methods=['POST'])
@login_required
def confirm():
    id = request.form['id']
    expert = current_user.get_id_int()

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.expert_confirm(id=id, expert_id=expert)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['newbie'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/pay', methods=['POST'])
@login_required
def pay():
    id = request.form['id']
    newbie = current_user.get_id_int()
    price = float(request.form['price'])
    order_id = request.form['order_id']

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.newbie_pay(id=id, newbie_id=newbie, price=price, order_id=order_id)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/deliver', methods=['POST'])
@login_required # TODO change to admin required
def deliver():
    id = request.form['id']
    record_id = request.form['record_id']

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.platform_deliver(id=id, record_id=record_id)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        appointment_change_event_notify(current_app, data, data['newbie'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/comment', methods=['POST'])
@login_required
def comment():
    id = request.form['id']
    newbie = current_user.get_id_int()
    content = request.form['content']
    rating = float(request.form['rating'])

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.newbie_comment(id=id, newbie_id=newbie, content=content, rating=rating)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/dispute', methods=['POST'])
@login_required
def dispute():
    id = request.form['id']
    newbie = current_user.get_id_int()
    content = request.form['content']

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.newbie_dispute(id=id, newbie_id=newbie, content=content)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/handle_dispute', methods=['POST'])
@login_required
@admin_required
def handle_dispute():
    id = request.form['id']
    agree = True if request.form['agree'] == 'true' else False
    content = request.form['content']

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.platform_handle_dispute(id=id, agree=agree, content=content)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        appointment_change_event_notify(current_app, data, data['newbie'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/finish', methods=['POST'])
@login_required # TODO change to admin required
def finish():
    id = request.form['id']

    app_ops = AppointmentOps(session=db.session)
    succeed = app_ops.platform_finish_it(id=id)
    if succeed:
        data = app_ops.get_appointment(id).to_dict()
        appointment_change_event_notify(current_app, data, data['expert'])
        appointment_change_event_notify(current_app, data, data['newbie'])
        return data

    return {'error': 'Failed to update appointment'}, 400

@bp.route('/', methods=['GET'])
@login_required
def get():
    id = request.args.get('id')

    app_ops = AppointmentOps(session=db.session)
    appointment = app_ops.get_appointment(id=id)
    if appointment is not None:
        return appointment.to_dict()

    return {'error': 'Failed to get appointment'}, 400

@bp.route('/check_balances', methods=['GET'])
@login_required
def check_balances():
    balance_ops = BalanceOps(session=db.session)
    if balance_ops.check_all():
        return {'error': 'succeed'}
    return {'error': 'failed'}, 400

@bp.route('/balance', methods=['GET'])
@login_required
def get_balance():
    user_id = current_user.get_id_int()
    balance_ops = BalanceOps(session=db.session)
    return balance_ops.balance_of(user_id=user_id)

@bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    user_id = current_user.get_id_int()
    amount = float(request.form['amount'])
    order_id = "no such id" # TODO fix this
    balance_ops = BalanceOps(session=db.session)
    succeed = balance_ops.withdraw(user=user_id, amount=amount, order_id=order_id)
    if succeed:
        # TODO call alipay payment methods
        return {"error": "succeed"}
    else:
        return {"error": "failed to withdraw"}, 400

@bp.route('/as_expert', methods=['GET'])
@login_required
def get_as_expert():
    expert = current_user.get_id_int()
    app_ops = AppointmentOps(session=db.session)
    appointments = app_ops.get_appointments_of_expert(expert=expert)
    return appointments

@bp.route('/as_newbie', methods=['GET'])
@login_required
def get_as_newbie():
    newbie = current_user.get_id_int()
    app_ops = AppointmentOps(session=db.session)
    appointments = app_ops.get_appointments_of_newbie(newbie=newbie)
    return appointments

@bp.route('/mine', methods=['GET'])
@login_required
def get_mine():
    user_id = current_user.get_id_int()
    app_ops = AppointmentOps(session=db.session)
    appointments = app_ops.get_appointments_of_mine(my_id=user_id)
    return appointments

@bp.route('/disputed', methods=['GET'])
@login_required
@admin_required
def get_disputed():
    app_ops = AppointmentOps(session=db.session)
    appointments = app_ops.get_appointments_disputed()
    return appointments

@bp.route('/deliver_videos', methods=['GET'])
@login_required
@admin_required
def get_deliver_videos():
    appid = request.args.get('appid')
    directory = os.path.join(
        current_app.instance_path,
        current_app.config['LIVEKIT_RECORDS_PATH'],
        appid)
    files = sorted(Path(directory).iterdir(), key=os.path.getmtime)
    result = []
    for file in files:
        if file.name.endswith('.mp4'):
            result.append(file.name)
    return result

@bp.route('/deliver_video', methods=['GET'])
@login_required
@admin_required
def get_deliver_video():
    appid = request.args.get('appid')
    video = request.args.get('video')
    video_path = os.path.join(
        current_app.instance_path,
        current_app.config['LIVEKIT_RECORDS_PATH'],
        appid, video)
    print(f'video_path, {video_path}')
    return send_file(video_path, mimetype='video/mp4')

@bp.route('/waiting_finish', methods=['GET'])
@login_required
@admin_required
def get_waiting_finish():
    app_ops = AppointmentOps(session=db.session)
    appointments = app_ops.get_appointments_waiting_finish()
    return appointments

@bp.route('/comments_of', methods=['GET'])
@login_required
def get_comments_of():
    expert = int(request.args.get('expert'))

    app_ops = AppointmentOps(session=db.session)
    comments = app_ops.get_comments_of(expert=expert)
    return comments

@bp.route('/comments_for_community', methods=['GET'])
@login_required
def get_comments_for_community():
    offset = request.args.get('offset', 0)
    limit = request.args.get('limit', 10)

    app_ops = AppointmentOps(session=db.session)
    comments = app_ops.get_comments_for_community(offset=offset, limit=limit)
    return comments
