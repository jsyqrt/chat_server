from flask import Blueprint, request, Response, current_app, stream_with_context
from flask_login import login_required, current_user
import json
import time
from datetime import datetime
from sqlalchemy import desc
import uuid

from zchat.db import db
from zchat.models.chat import ChatSession, ChatMessage
from zchat.apis.llm import chat_with_llm_stream

bp = Blueprint('aichat_stream', __name__, url_prefix='/aichat')

@bp.route('/chat', methods=['POST'])
@login_required
def chat_with_ai():
    """与AI聊天并获取流式响应"""
    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id', None)
    chat_context = data.get('chat_context', None)

    if not user_message:
        return Response(json.dumps({"error": "消息内容不能为空"}),
                        status=400, mimetype='application/json')

    # 获取或创建聊天会话
    session = None
    if session_id:
        session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()

    if session is None:
        return Response(json.dumps({"error": "会话不存在或无权访问"}),
                        status=404, mimetype='application/json')

    # 保存用户消息
    user_chat_message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        sender_type='user',
        content=user_message,
        timestamp=time.time(),
        message_metadata= {
            "roadmap_id": chat_context.get("roadmap_id"),
            "node_id": chat_context.get("node_id"),
            "node_path": chat_context.get("node_path"),
        } if chat_context else {}
    )
    db.session.add(user_chat_message)
    db.session.commit()

    # 获取会话历史记录
    history = get_chat_history(session.id)

    if chat_context:
        history.extend(chat_msgs_from_context(chat_context))

    # 准备AI响应消息记录
    ai_message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        sender_type='ai',
        content="",  # 将在流式响应完成后更新
        timestamp=time.time(),
    )
    db.session.add(ai_message)
    session.updated_at = time.time()
    db.session.commit()

    # 创建流式响应
    def generate():
        full_response = ""

        # current_app.logger.debug(f"history: {history}, user_message: {user_message}")

        # 调用LLM API并处理流式响应
        for chunk in chat_with_llm_stream(user_message, history=history, model="qwen-2.5-32b", max_tokens=4096, platform="siliconflow"):
            if chunk:
                full_response += chunk
                yield f"data: {json.dumps({'text': chunk, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"

        # 流式响应结束后，更新AI消息内容
        ai_message.content = full_response
        db.session.commit()

        current_app.logger.debug(f"ai_message: {ai_message.content}")

        # 发送完成信号
        yield f"data: {json.dumps({'done': True, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})

def get_chat_history(session_id, max_messages=20):
    """获取聊天历史记录用于AI上下文"""
    messages = ChatMessage.query.filter_by(session_id=session_id) \
                            .order_by(desc(ChatMessage.timestamp)) \
                            .limit(max_messages).all()

    # 构造历史记录格式
    history = []
    for message in messages:
        role = "user" if message.sender_type == "user" else "assistant"
        history.append({"role": role, "content": message.content})

    history.reverse()

    return history

def chat_msgs_from_context(chat_context):
    roadmap_title = chat_context.get("roadmap_title")
    node_title = chat_context.get("node_title")
    node_path = chat_context.get("node_path")
    node_description = chat_context.get("node_description")

    return [
        {"role": "user", "content": f"我正在学习一个大的主题：「{roadmap_title}」，目前的学习路径是「{node_path}」，请给我解释一下这个主题：「{node_title}」"},
        {"role": "assistant", "content": f"{node_description}"}
    ]
