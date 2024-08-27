import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

import jwt
from flask import render_template, request, current_app, Blueprint
from livekit import api as livekit_api

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.models import *
from zchat.websocket import socketio

bp = Blueprint('chat', __name__, url_prefix='/chat')
executor = ThreadPoolExecutor()

async def run_async(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    loop.create_task(func(fut, *args, **kwargs))
    return await fut

@bp.route('/test', methods=['GET'])
@login_required
def test_chat():
    return render_template('chat.html')

@bp.route('/call_records', methods=['GET'])
@login_required
def call_records():
    appid = request.args.get('appid')

    call_record_ops = CallRecordOps(session=db.session)
    records = call_record_ops.get_records(appointment_id=appid)
    return records

async def livekit_create_room(fut, app, name: str):
    host = app.config['LIVEKIT_HOST']
    api_key = app.config['LIVEKIT_API_KEY']
    secret = app.config['LIVEKIT_API_SECRET']

    lkapi = livekit_api.LiveKitAPI(
        url=host,
        api_key=api_key,
        api_secret=secret,
    )

    room_info = await lkapi.room.create_room(
        livekit_api.CreateRoomRequest(
            name=name,
            empty_timeout=1000,
            departure_timeout=1000,
            egress=livekit_api.RoomEgress(
                room=livekit_api.RoomCompositeEgressRequest(
                    room_name=name,
                    file_outputs=[
                        livekit_api.EncodedFileOutput(
                            filepath="/out/records/{room_name}/{time}.mp4",
                        )
                    ]
                )
            )
        ),
    )

    await lkapi.aclose()
    fut.set_result(room_info)

async def livekit_list_rooms(fut, app):
    host = app.config['LIVEKIT_HOST']
    api_key = app.config['LIVEKIT_API_KEY']
    secret = app.config['LIVEKIT_API_SECRET']

    lkapi = livekit_api.LiveKitAPI(
        url=host,
        api_key=api_key,
        api_secret=secret,
    )

    results = await lkapi.room.list_rooms(livekit_api.ListRoomsRequest())
    await lkapi.aclose()
    fut.set_result(results)

async def livekit_list_egress_of(fut, app, room_name):
    host = app.config['LIVEKIT_HOST']
    api_key = app.config['LIVEKIT_API_KEY']
    secret = app.config['LIVEKIT_API_SECRET']

    lkapi = livekit_api.LiveKitAPI(
        url=host,
        api_key=api_key,
        api_secret=secret,
    )

    results = await lkapi.egress.list_egress(
        list=livekit_api.ListEgressRequest(
                    room_name=room_name
        )
    )
    await lkapi.aclose()
    fut.set_result(results)

async def livekit_stop_egress(fut, app, egress_id):
    host = app.config['LIVEKIT_HOST']
    api_key = app.config['LIVEKIT_API_KEY']
    secret = app.config['LIVEKIT_API_SECRET']

    lkapi = livekit_api.LiveKitAPI(
        url=host,
        api_key=api_key,
        api_secret=secret,
    )

    results = await lkapi.egress.stop_egress(
        stop=livekit_api.StopEgressRequest(
            egress_id=egress_id
        )
    )
    await lkapi.aclose()
    fut.set_result(results)

async def livekit_delete_room(fut, app, room_name):
    host = app.config['LIVEKIT_HOST']
    api_key = app.config['LIVEKIT_API_KEY']
    secret = app.config['LIVEKIT_API_SECRET']

    lkapi = livekit_api.LiveKitAPI(
        url=host,
        api_key=api_key,
        api_secret=secret,
    )

    results = await lkapi.room.delete_room(
        delete=livekit_api.DeleteRoomRequest(
            room=room_name
        )
    )
    await lkapi.aclose()
    fut.set_result(results)

def stop_egress_of(app, room_name):
    app.logger.debug(f'ready to stop egress of room {room_name}')
    egress = asyncio.run(run_async(livekit_list_egress_of, app, room_name))
    for item in egress.items:
        if item.status ==  livekit_api.EGRESS_ACTIVE:
            app.logger.debug(f'ready to stop egress of room {room_name} with egress id {item.egress_id}')
            egress = asyncio.run(run_async(livekit_stop_egress, app, item.egress_id))

def stop_livekit_egress_room(app, room_name):
    stop_egress_of(app, room_name)
    app.logger.debug(f'ready to delete room {room_name}')
    asyncio.run(run_async(livekit_delete_room, app, room_name))

@bp.route('/get_token')
@login_required
def getToken():
    api_key = current_app.config['LIVEKIT_API_KEY']
    secret = current_app.config['LIVEKIT_API_SECRET']

    id = current_user.get_id()
    user_name = request.args.get('name') # TODO this may be dangerous
    appointment_id = request.args.get('appid')

    current_app.logger.debug(f'get token for user {id}, {user_name} for appointment {appointment_id}')

    # create room if necessary, with egress open
    rooms = asyncio.run(run_async(livekit_list_rooms, current_app))
    current_app.logger.debug(f'get all rooms {rooms}')

    need_create = True
    for room in rooms.rooms:
        if room.name == appointment_id:
            current_app.logger.debug(f'no need to create room, already exists {room.name}')
            need_create = False

    if need_create:
        room_info = asyncio.run(run_async(livekit_create_room, current_app, appointment_id))
        current_app.logger.debug(f'create room with info \n{room_info}')

    token = livekit_api.AccessToken(api_key, secret) \
        .with_identity(id) \
        .with_name(user_name) \
        .with_grants(livekit_api.VideoGrants(
            room_join=True,
            room=appointment_id,
        ))
    return token.to_jwt()

@bp.route('/latest_read_msg', methods=['GET'])
@login_required
def get_latest_read_msg():
    user_id = current_user.get_id_int()
    sender = int(request.args.get('sender'))
    receiver = int(request.args.get('receiver'))
    if user_id != sender and user_id != receiver:
        return {'error': 'Unauthorized'}, 401

    current_app.logger.debug(f'get latest read msg for {sender} and {receiver}')

    latest_read_msg_ops = LatestReadMsgOps(session=db.session)
    latest_read_msg = latest_read_msg_ops.get_latest_read_msg(sender=sender, receiver=receiver)
    return latest_read_msg

def get_user_id_from_jwt(app, token):
    return jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms="HS256")['user_id']

@socketio.on('connect')
def handle_connect():
    uid = get_user_id_from_jwt(current_app, request.headers["token"])
    sid = request.sid
    current_app.add_user_session(uid, sid)

    current_app.logger.debug(f'{request.headers["token"]}')
    current_app.logger.debug(f'{request.sid}')
    current_app.logger.debug(f'Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    current_app.logger.debug(f'Client disconnected')
    current_app.logger.debug(f'{request.headers["token"]}')

    uid = get_user_id_from_jwt(current_app, request.headers["token"])
    sid = request.sid
    current_app.remove_user_session(uid)

@socketio.on('login')
def handle_login(msg):
    current_app.logger.debug(f'hello login')

    # Save session id
    uid = get_user_id_from_jwt(current_app, msg['token'])
    sid = request.sid
    current_app.add_user_session(uid, sid)

    # Notify user there are n msgs to receive
    msgs = current_app.unsent_msgs.get(uid, [])
    socketio.emit('notice', {'type': 'msg_to_get', 'count': len(msgs)}, to=sid)

    current_app.logger.debug(f'Client connected {uid}, {sid}')

@socketio.on('logout')
def handle_logout(msg):
    # Remove session id from session map
    uid = get_user_id_from_jwt(current_app, msg['token'])
    current_app.remove_user_session(uid)

    current_app.logger.debug(f'Client disconnected {uid}, {request.sid}')

@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    data_json = data
    current_app.logger.debug(f'Received JSON data: {data_json}')

    from_id  = get_user_id_from_jwt(current_app, data_json['token'])
    to_id = data_json.get('receiver', 0)
    msg = data_json.get('msg', 'None')
    msg_type = data_json.get('msg_type', 0)
    timestamp = data_json.get('timestamp', time.time())

    # Send msg to dest
    msg_dict = {'sender': from_id, 'receiver': to_id, 'msg': msg, 'msg_type': msg_type, 'timestamp': timestamp}

    chatmsg_ops = ChatMsgOps(session=db.session)
    chatmsg_ops.add_msg(sender=from_id, receiver=to_id, msg=msg, msg_type=msg_type, timestamp=timestamp)

    # Send to self
    is_send_to_self = from_id == to_id
    if is_send_to_self:
        return

    to_sid = current_app.get_user_session(to_id)
    if to_sid is not None:
        # If the user is online
        current_app.logger.debug(f'user is online: {to_id}')

        socketio.emit('msg', msg_dict, to=to_sid)
    else:
        # Save to a map, waiting the user online again
        # TODO change the map to a db table, in case server is down
        current_app.logger.debug(f'user is offline: {to_id}')

        msgs = current_app.unsent_msgs.get(to_id, [])
        msgs.append(msg_dict)

        current_app.unsent_msgs[to_id] = msgs

@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    current_app.logger.debug(f'mark_as_read: {data}')
    data_json = data
    current_app.logger.debug(f'Received JSON data: {data_json}')

    uid = get_user_id_from_jwt(current_app, data_json['token'])
    to_id = data_json.get('receiver', 0)
    if to_id != uid:
        current_app.logger.error(f'mark_as_read to_id != uid, {to_id}, {uid}')
        return

    from_id = data_json.get('sender', 0)
    timestamp = data_json.get('timestamp', time.time())

    latest_read_msg_ops = LatestReadMsgOps(session=db.session)
    latest_read_msg_ops.update_latest_read_msg(sender=from_id, receiver=to_id, timestamp=timestamp)

    sender_sid = current_app.get_user_session(from_id)
    if sender_sid is not None:
        socketio.emit('latest_read_time', {'sender': from_id, 'receiver': to_id, 'timestamp': timestamp}, to=sender_sid)
    else:
        current_app.logger.debug(f'sender is offline: {from_id}')

@socketio.on('get_latest_read_time')
def handle_get_latest_read_time(data):
    current_app.logger.debug(f'get_latest_read_time: {data}')
    sid = request.sid
    data_json = data
    current_app.logger.debug(f'Received JSON data: {data_json}')

    uid = get_user_id_from_jwt(current_app, data_json['token'])
    from_id = data_json.get('sender', 0)
    if from_id != uid:
        current_app.logger.error(f'get_latest_read_time from_id != uid, {from_id}, {uid}')
        return

    receiver = data_json.get('receiver', 0)

    latest_read_msg_ops = LatestReadMsgOps(session=db.session)
    latest_read_msg = latest_read_msg_ops.get_latest_read_msg(sender=from_id, receiver=receiver)
    socketio.emit('latest_read_time', latest_read_msg, to=sid)

@socketio.on('get_messages')
def handle_all_messages(data):
    current_app.logger.debug(f'get_messages: {data}')
    sid = request.sid
    data_json = data
    current_app.logger.debug(f'Received JSON data: {data_json}')

    p1_id = data_json.get('p1', 0)
    p2_id = data_json.get('p2', 0)
    before_timestamp = data_json.get('before_timestamp', time.time())
    latest_n = data_json.get('latest_n', 100)

    chatmsg_ops = ChatMsgOps(session=db.session)
    msgs = chatmsg_ops.get_msgs(p1=p1_id, p2=p2_id, before_timestamp=before_timestamp, latest_n=latest_n)

    for msg in msgs:
        socketio.emit('msg_response', msg, to=sid)

@socketio.on('makeCall')
def makeCall(data):
    callerId = data.get('callerId')
    calleeId = data.get('calleeId')
    isVideo = data.get('isVideo')
    sdpOffer = data.get('sdpOffer')
    appid = data.get('appid')

    current_app.logger.debug(f"got makeCall from {callerId} to {calleeId}")

    call_record_ops = CallRecordOps(session=db.session)
    call_record_id = call_record_ops.start(
        appointment_id=appid,
        type=1 if isVideo else 0,
        caller=callerId,
        callee=calleeId,
        timestamp=time.time(),
    )

    current_app.logger.debug(f"call_record_id is {call_record_id}")

    from_sid = current_app.get_user_session(callerId)
    to_sid = current_app.get_user_session(calleeId)
    if to_sid is not None:
        socketio.emit('newCall', {"isVideo": isVideo, "callerId": callerId, "sdpOffer": sdpOffer, "calleeId": calleeId, "appid": appid}, to=to_sid)
        current_app.logger.debug(f"sending {sdpOffer} to {calleeId}")
    else:
        socketio.emit('callLeaved', {'calleeOnline': False, "callerId": callerId, "calleeId": calleeId}, to=from_sid)
        current_app.logger.debug(f"callee is not online {calleeId}")

@socketio.on('acceptCall')
def acceptCall(data):
    calleeId = data.get('calleeId')
    appid = data.get('appid')

    current_app.logger.debug(f"got acceptCall from {calleeId}")

    call_record_ops = CallRecordOps(session=db.session)
    call_record_id = call_record_ops.accept(
        appointment_id=appid,
        timestamp=time.time(),
    )
    current_app.logger.debug(f"call_record_id is {call_record_id}")

@socketio.on('leaveCall')
def leaveCall(data):
    callerId = data.get('callerId')
    calleeId = data["calleeId"]
    fromCaller = data["fromCaller"]
    appid = data.get('appid')
    reason = data.get('reason')

    current_app.logger.debug(f"got leaveCall")

    if fromCaller:
        to_sid = current_app.get_user_session(calleeId)
    else:
        to_sid = current_app.get_user_session(callerId)

    if to_sid is not None:
        current_app.logger.debug(f"sending callLeaved to {to_sid}, fromCaller {fromCaller}, {callerId}, {calleeId}")
        socketio.emit('callLeaved', {"fromCaller": fromCaller, "appid":appid, "reason": reason, "callerId": callerId, "calleeId": calleeId}, to=to_sid)
    else:
        current_app.logger.debug(f"opposite is not online {to_sid}")

    call_record_ops = CallRecordOps(session=db.session)
    call_record_id = call_record_ops.end(
        appointment_id=appid,
        by_user=callerId if fromCaller else calleeId,
        timestamp=time.time(),
    )
    current_app.logger.debug(f"call_record_id is {call_record_id}")

    try:
        stop_livekit_egress_room(app=current_app, room_name=appid)
    except Exception as e:
        current_app.logger.error(f"failed to stop livekit egress room {appid}, error {e}")
