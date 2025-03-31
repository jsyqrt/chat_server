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
    session_id = data.get('session_id')
    session_data = data.get('session_data', {})

    if not user_message:
        return Response(json.dumps({"error": "消息内容不能为空"}),
                        status=400, mimetype='application/json')

    # 获取或创建聊天会话
    session = None
    if session_id:
        session = ChatSession.query.filter_by(id=session_id, user_id=current_user.get_id_int()).first()
        if not session:
            return Response(json.dumps({"error": "会话不存在或无权访问"}),
                            status=404, mimetype='application/json')
    else:
        # 创建新会话
        title = session_data.get('title', f"与AI的对话 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")
        session = ChatSession(
            id=str(uuid.uuid4()),
            title=title,
            type=session_data.get('type', 'general'),
            user_id=current_user.get_id_int(),
            session_metadata=session_data.get('session_metadata', {})
        )
        db.session.add(session)
        db.session.commit()

    # 保存用户消息
    user_chat_message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        sender_type='user',
        content=user_message
    )
    db.session.add(user_chat_message)
    db.session.commit()

    # 获取会话历史记录
    history = get_chat_history(session.id)

    # 准备AI响应消息记录
    ai_message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        sender_type='ai',
        content=""  # 将在流式响应完成后更新
    )
    db.session.add(ai_message)
    db.session.commit()

    # 创建流式响应
    def generate():
        full_response = ""

        # 调用LLM API并处理流式响应
        for chunk in chat_with_llm_stream(user_message, history=history, model="qwen-2.5-32b", max_tokens=4096, platform="siliconflow"):
            if chunk:
                full_response += chunk
                current_app.logger.debug(f"chunk: {chunk}")
                yield f"data: {json.dumps({'text': chunk, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"

        # 流式响应结束后，更新AI消息内容
        ai_message.content = full_response
        db.session.commit()

        # 更新会话的更新时间
        session.updated_at = time.time()
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

    return history