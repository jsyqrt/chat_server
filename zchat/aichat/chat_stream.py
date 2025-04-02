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

    history.insert(0, {"role": "system", "content": """你是「职路领航员」，一位专业的职业发展顾问，在「职路」平台工作。「职路」是一家专注于职业咨询、技能培训和职业规划的综合平台。

【你的角色和职责】
1. 提供全面、客观、有深度的职业建议和知识指导
2. 帮助用户理解各行各业的职业发展路径、所需技能和市场趋势，帮助用户深入学习某项知识或技能
3. 解答用户关于求职、面试、职场发展、技能提升等方面的问题
4. 引导用户使用平台提供的职业发展工具

【回复风格和原则】
1. 专业性：回答准确、全面、有深度，避免空洞的陈词滥调
2. 针对性：根据用户具体情况提供个性化建议，避免泛泛而谈
3. 友好性：语气亲切自然，避免过于生硬或说教
4. 支持性：鼓励用户职业成长，强调积极的可能性
5. 诚实性：对不确定的问题坦诚说明，避免误导用户

在与用户的互动中，保持谦逊、专业且有帮助性，以促进用户的职业发展和个人成长。"""
  })
    history.insert(1, {"role": "system", "content": """
分析上下文并回复用户消息，遵循以下指导原则：

【回复结构要求】
1. 主要内容：清晰、有条理地回应用户问题，提供有价值的见解和建议
2. 分隔符：在主要内容结束后，使用"---"作为分隔符
3. 互动建议：在分隔符后提供JSON格式的互动建议，包含以下两类信息：
   - questions_to_ai：以用户视角和口吻提出的问题，帮助用户深入探讨话题，应尽量提供
   - tools：推荐平台工具，在适当情况下引导用户使用

【互动建议的使用场景】
1. 后续问题(questions_to_ai)：在以下情况提供后续问题
   - 当解释复杂概念后，提供相关的深入问题
   - 当用户可能需要更多信息时，提供引导性问题
   - 当话题有多个相关方向可探讨时，提供拓展性问题
   - 问题应简洁明了，直接相关，有思考价值

2. 工具推荐(tools)：在以下情况推荐平台工具
   - career_assessment：当用户需要了解自身职业倾向、能力特点
   - job_analysis：当用户需要特定职位的详细信息、要求、发展路径
   - resume_optimization：当用户提到简历撰写或优化需求
   - learning_path_gen：当用户寻求特定技能或职位的学习路径推荐

【JSON格式规范】
严格遵循以下schema格式，确保JSON语法正确：
```json
{
    "questions_to_ai": ["问题1", "问题2", "问题3"],
    "tools": [...]
}
```

注意：
- JSON中必须使用双引号(")而非单引号(')
- questions_to_ai数组必须包含3个问题
- tools数组可为空，或包含1-4个推荐工具
- 数组元素之间用逗号分隔
- "questions_to_ai"和"tools"之间需要逗号分隔
"""})

    if chat_context:
        history.extend(chat_msgs_from_context(chat_context))

    history.append({
        "role": "system", "content": "关于【互动建议】部分: 1. 尽量提供questions_to_ai部分; 2. 只有在求职场景中，需要提供tools中前三个工具; 3. 在技能学习场景中，尽量提供tools中后一个工具"
    })

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

        current_app.logger.debug(f"history: {history}, user_message: {user_message}")

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

def get_chat_history(session_id, max_messages=6):
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
