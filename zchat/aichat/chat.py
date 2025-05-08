from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc
import uuid
from zchat.models.base import db
from zchat.models.chat import ChatSession, ChatMessage
import time
from flask_babel import gettext as _

bp = Blueprint('aichat', __name__, url_prefix='/aichat')

@bp.route('/sessions', methods=['GET'])
@login_required
def get_chat_sessions():
    """获取当前用户的聊天会话列表"""
    # 获取查询参数
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    archived = request.args.get('archived', 'false')
    session_type = request.args.get('type')
    roadmap_id = request.args.get('roadmap_id', None)

    # 构建查询
    query = ChatSession.query.filter_by(user_id=current_user.get_id_int())

    # 应用过滤条件
    if session_type:
        query = query.filter_by(type=session_type)
    if archived is not None:
        is_archived = archived.lower() == 'true'
        query = query.filter_by(is_archived=is_archived)
    if roadmap_id:
        query = query.filter_by(roadmap_id=roadmap_id)

    # 按更新时间降序排序并分页
    sessions = query.order_by(desc(ChatSession.updated_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 获取每个会话的最后一条消息
    last_messages = []
    for session in sessions.items:
        last_message = ChatMessage.query.filter_by(session_id=session.id).order_by(desc(ChatMessage.timestamp)).first()
        last_messages.append(last_message.to_dict() if last_message else None)

    sessions_with_last_message = [
        (session, last_message)
        for session, last_message in zip(sessions.items, last_messages)
    ]

    # 去掉last_message为None的会话
    sessions = [{**session[0].to_dict(), "last_message": session[1]} for session in sessions_with_last_message if session[1] is not None]
    empty_sessions = [session for session in sessions_with_last_message if session[1] is None]
    for session in empty_sessions:
        if session[0].updated_at < time.time() - 60:
            db.session.delete(session[0])
            db.session.commit()
            current_app.logger.debug(f"删除会话: {session[0].id}")

    return jsonify({
        "sessions": sessions,
        "total": len(sessions),
    })

@bp.route('/sessions', methods=['POST'])
@login_required
def create_chat_session():
    """创建新的聊天会话"""
    data = request.json

    if not data.get('title'):
        return jsonify({"error": _("会话标题不能为空")}), 400

    current_app.logger.debug(f"create_chat_session: {data}")

    session = ChatSession(
        id=str(uuid.uuid4()),
        title=data.get('title'),
        type=data.get('type', 'general'),
        roadmap_id=data.get('roadmap_id', None),
        user_id=current_user.get_id_int(),
        session_metadata=data.get('session_metadata', {}),
        created_at=time.time(),
        updated_at=time.time()
    )

    db.session.add(session)
    db.session.commit()

    return jsonify(session.to_dict()), 201

@bp.route('/sessions/<string:session_id>', methods=['GET'])
@login_required
def get_chat_session(session_id):
    """获取特定聊天会话的详情"""
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()
    if not session:
        return jsonify({"error": _("会话不存在或无权访问")}), 404

    return jsonify(session.to_dict())

@bp.route('/sessions/<string:session_id>', methods=['PUT'])
@login_required
def update_chat_session(session_id):
    """更新聊天会话信息"""
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()
    if not session:
        return jsonify({"error": _("会话不存在或无权访问")}), 404

    data = request.json

    if 'title' in data:
        session.title = data['title']
    if 'type' in data:
        session.type = data['type']
    if 'is_archived' in data:
        session.is_archived = data['is_archived']
    if 'session_metadata' in data:
        session.session_metadata = data['session_metadata']

    db.session.commit()

    return jsonify(session.to_dict())

@bp.route('/sessions/<string:session_id>', methods=['DELETE'])
@login_required
def delete_chat_session(session_id):
    """删除聊天会话"""
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()
    if not session:
        return jsonify({"error": _("会话不存在或无权访问")}), 404

    db.session.delete(session)
    db.session.commit()

    return jsonify({"message": _("会话已删除")}), 200

@bp.route('/sessions/<string:session_id>/messages', methods=['GET'])
@login_required
def get_chat_messages(session_id):
    """获取特定会话的聊天记录"""
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()
    if not session:
        return jsonify({"error": _("会话不存在或无权访问")}), 404

    # 获取分页参数
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))

    # 查询消息并按时间排序
    messages = ChatMessage.query.filter_by(session_id=session_id) \
                              .order_by(desc(ChatMessage.timestamp)) \
                              .offset(offset).limit(limit).all()

    # 获取总消息数
    total_messages = ChatMessage.query.filter_by(session_id=session_id).count()

    return jsonify({
        "messages": [message.to_dict() for message in messages],
        "total": total_messages,
        "offset": offset,
        "limit": limit
    })