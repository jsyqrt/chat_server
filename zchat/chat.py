import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

from flask import render_template, request, current_app, Blueprint
from livekit import api as livekit_api

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.models import *

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

def init_app(app):
    app.unsent_msgs = app.multi_processing_manager.dict()

    @app.socketio.on('connect')
    @login_required
    def handle_connect():
        # Save session id
        uid = current_user.get_id_int()
        sid = request.sid
        app.user_to_session[uid] = sid

        # Notify user there are n msgs to receive
        msgs = app.unsent_msgs.get(uid, [])
        app.socketio.emit('notice', {'type': 'msg_to_get', 'count': len(msgs)}, to=sid)

        app.logger.debug(f'Client connected {uid}, {sid}')

    @app.socketio.on('disconnect')
    @login_required
    def handle_disconnect():
        # Remove session id from session map
        uid = current_user.get_id_int()
        app.user_to_session.pop(uid)

        app.logger.debug(f'Client disconnected {uid}, {request.sid}')

    @app.socketio.on('send_message')
    @login_required
    def handle_send_message(data):
        sid = request.sid
        data_json = data
        app.logger.debug(f'Received JSON data: {data_json}')

        from_id = current_user.get_id_int()
        to_id = data_json.get('receiver', 0)
        msg = data_json.get('msg', 'None')
        msg_type = data_json.get('msg_type', 0)

        # TODO what if from_id == to_id?

        # Send msg to dest
        msg_dict = {'sender': from_id, 'receiver': to_id, 'msg': msg, 'msg_type': msg_type, 'timestamp': time.time()}

        chatmsg_ops = ChatMsgOps(session=db.session)
        chatmsg_ops.add_msg(sender=from_id, receiver=to_id, msg=msg, msg_type=msg_type, timestamp=time.time())

        to_sid = app.user_to_session.get(to_id, None)
        if to_sid is not None:
            # If the user is online
            app.logger.debug(f'user is online: {to_id}')

            app.socketio.emit('msg', msg_dict, to=to_sid)
        else:
            # Save to a map, waiting the user online again
            # TODO change the map to a db table, in case server is down
            app.logger.debug(f'user is offline: {to_id}')

            msgs = app.unsent_msgs.get(to_id, [])
            msgs.append(msg_dict)

            app.unsent_msgs[to_id] = msgs

    @app.socketio.on('get_messages')
    @login_required
    def handle_all_messages(data):
        app.logger.debug(f'get_messages: {data}')
        sid = request.sid
        data_json = data
        app.logger.debug(f'Received JSON data: {data_json}')

        p1_id = data_json.get('p1', 0)
        p2_id = data_json.get('p2', 0)
        before_timestamp = data_json.get('before_timestamp', time.time())
        latest_n = data_json.get('latest_n', 100)

        chatmsg_ops = ChatMsgOps(session=db.session)
        msgs = chatmsg_ops.get_msgs(p1=p1_id, p2=p2_id, before_timestamp=before_timestamp, latest_n=latest_n)

        for msg in msgs:
            app.socketio.emit('msg_response', msg, to=sid)

    @app.socketio.on('makeCall')
    @login_required
    def makeCall(data):
        callerId = data.get('callerId')
        calleeId = data.get('calleeId')
        isVideo = data.get('isVideo')
        sdpOffer = data.get('sdpOffer')
        appid = data.get('appid')

        app.logger.debug(f"got makeCall from {callerId} to {calleeId}")

        call_record_ops = CallRecordOps(session=db.session)
        call_record_id = call_record_ops.start(
            appointment_id=appid,
            type=1 if isVideo else 0,
            caller=callerId,
            callee=calleeId,
            timestamp=time.time(),
        )

        app.logger.debug(f"call_record_id is {call_record_id}")

        from_sid = app.user_to_session.get(callerId, None)
        to_sid = app.user_to_session.get(calleeId, None)
        if to_sid is not None:
            app.socketio.emit('newCall', {"isVideo": isVideo, "callerId": callerId, "sdpOffer": sdpOffer, "calleeId": calleeId, "appid": appid}, to=to_sid)
            app.logger.debug(f"sending {sdpOffer} to {calleeId}")
        else:
            app.socketio.emit('callLeaved', {'calleeOnline': False, "callerId": callerId, "calleeId": calleeId}, to=from_sid)
            app.logger.debug(f"callee is not online {calleeId}")

    @app.socketio.on('acceptCall')
    @login_required
    def acceptCall(data):
        calleeId = data.get('calleeId')
        appid = data.get('appid')

        app.logger.debug(f"got acceptCall from {calleeId}")

        call_record_ops = CallRecordOps(session=db.session)
        call_record_id = call_record_ops.accept(
            appointment_id=appid,
            timestamp=time.time(),
        )
        app.logger.debug(f"call_record_id is {call_record_id}")

    @app.socketio.on('leaveCall')
    @login_required
    def leaveCall(data):
        callerId = data.get('callerId')
        calleeId = data["calleeId"]
        fromCaller = data["fromCaller"]
        appid = data.get('appid')

        app.logger.debug(f"got leaveCall")

        if fromCaller:
            to_sid = app.user_to_session.get(calleeId, None)
        else:
            to_sid = app.user_to_session.get(callerId, None)

        if to_sid is not None:
            app.logger.debug(f"sending callLeaved to {to_sid}, fromCaller {fromCaller}, {callerId}, {calleeId}")
            app.socketio.emit('callLeaved', {"callerId": callerId, "calleeId": calleeId}, to=to_sid)
        else:
            app.logger.debug(f"opposite is not online {to_sid}")

        call_record_ops = CallRecordOps(session=db.session)
        call_record_id = call_record_ops.end(
            appointment_id=appid,
            by_user=callerId if fromCaller else calleeId,
            timestamp=time.time(),
        )
        app.logger.debug(f"call_record_id is {call_record_id}")

        try:
            stop_livekit_egress_room(app=app, room_name=appid)
        except Exception as e:
            app.logger.error(f"failed to stop livekit egress room {appid}, error {e}")
