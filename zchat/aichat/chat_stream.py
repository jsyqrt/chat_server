from flask import Blueprint, request, Response, current_app, stream_with_context, jsonify, g
from flask_login import login_required, current_user
import json
import time
from datetime import datetime
from sqlalchemy import desc
import uuid
import logging
import traceback
from flask_babel import gettext as _

from zchat.models.base import db
from zchat.models.chat import ChatSession, ChatMessage
from zchat.apis.llm import chat_with_llm_stream
from zchat.models.points import ServiceType
from zchat.points import check_points_sufficient, consume_points_for_service

bp = Blueprint('aichat_stream', __name__, url_prefix='/aichat')

def get_user_lang():
    return getattr(g, 'lang', 'zh_CN')

@bp.route('/chat', methods=['POST'])
@login_required
def chat_with_ai():
    """与AI聊天并获取流式响应"""
    try:
        data = request.json
        if not data:
            return Response(json.dumps({"error": _("无效的请求数据")}),
                         status=400, mimetype='application/json')

        user_message = data.get('message')
        session_id = data.get('session_id', None)
        chat_context = data.get('chat_context', None)
        message_metadata= {
            "roadmap_id": chat_context.get("roadmap_id", None) if chat_context else None,
            "node_id": chat_context.get("node_id", None) if chat_context else None,
            "node_path": chat_context.get("node_path", None) if chat_context else None,
            "ref_msg_id": chat_context.get("ref_msg_id", None) if chat_context else None,
            "ref_msg_content": chat_context.get("ref_msg_content", None) if chat_context else None,
        }

        # 验证必要参数
        if not user_message:
            return Response(json.dumps({"error": _("消息内容不能为空")}),
                            status=400, mimetype='application/json')

        if not session_id:
            return Response(json.dumps({"error": _("会话ID不能为空")}),
                            status=400, mimetype='application/json')

        user_id = current_user.get_id_int()

        # 检查积分是否足够
        try:
            sufficient, message = check_points_sufficient(user_id, ServiceType.AI_CHAT.value)
            if not sufficient:
                return Response(json.dumps({"error": message, "points_required": True}),
                                status=402, mimetype='application/json')
        except Exception as e:
            current_app.logger.error(f"积分检查失败: {str(e)}")
            return Response(json.dumps({"error": _("积分检查失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # 获取聊天会话
        try:
            session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
            if session is None:
                return Response(json.dumps({"error": _("会话不存在或无权访问")}),
                                status=404, mimetype='application/json')
        except Exception as e:
            current_app.logger.error(f"查询会话失败: {str(e)}")
            return Response(json.dumps({"error": _("查询会话失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # 保存用户消息
        user_chat_message = None
        try:
            user_chat_message = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session.id,
                sender_type='user',
                content=user_message,
                timestamp=time.time(),
                message_metadata=message_metadata,
            )
            db.session.add(user_chat_message)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"保存用户消息失败: {str(e)}")
            return Response(json.dumps({"error": _("保存用户消息失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # 获取会话历史记录
        try:
            history = get_chat_history(session.id)
        except Exception as e:
            current_app.logger.error(f"获取聊天历史失败: {str(e)}")
            return Response(json.dumps({"error": _("获取聊天历史失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # Get user's language preference
        user_lang = get_user_lang()

        # Add system prompt based on user language
        if user_lang == 'en':
            system_role_prompt = """You are "VoyLead Assistant", a professional career development advisor working on the "VoyLead" platform. "VoyLead" is a comprehensive platform focused on career consulting, skills training, and career planning.

【Your Role and Responsibilities】
1. Provide comprehensive, objective, and in-depth career advice and knowledge guidance
2. Help users understand career development paths, required skills, and market trends in various industries, and help users learn specific knowledge or skills in depth
3. Answer user questions about job hunting, interviews, career development, skill improvement, etc.
4. Guide users to use the career development tools provided by the platform

【Response Style and Principles】
1. Professionalism: Answers should be accurate, comprehensive, and in-depth, avoiding empty clichés
2. Relevance: Provide personalized advice based on the user's specific situation, avoiding generalizations
3. Friendliness: Use a warm and natural tone, avoiding being too rigid or preachy
4. Supportiveness: Encourage users' career growth and emphasize positive possibilities
5. Honesty: Be honest about uncertain questions and avoid misleading users

IMPORTANT: Please respond in English as the user has selected English as their preferred language.

In your interactions with users, remain humble, professional, and helpful to promote their career development and personal growth."""
        elif user_lang == 'zh_TW':
            system_role_prompt = """你是「職路領航員」，一位專業的職業發展顧問，在「職路」平台工作。「職路」是一家專注於職業諮詢、技能培訓和職業規劃的綜合平台。

【你的角色和職責】
1. 提供全面、客觀、有深度的職業建議和知識指導
2. 幫助用戶理解各行各業的職業發展路徑、所需技能和市場趨勢，幫助用戶深入學習某項知識或技能
3. 解答用戶關於求職、面試、職場發展、技能提升等方面的問題
4. 引導用戶使用平台提供的職業發展工具

【回覆風格和原則】
1. 專業性：回答準確、全面、有深度，避免空洞的陳詞濫調
2. 針對性：根據用戶具體情況提供個性化建議，避免泛泛而談
3. 友好性：語氣親切自然，避免過於生硬或說教
4. 支持性：鼓勵用戶職業成長，強調積極的可能性
5. 誠實性：對不確定的問題坦誠說明，避免誤導用戶

重要：請使用繁體中文回覆，因為用戶選擇了繁體中文作為偏好語言。

在與用戶的互動中，保持謙遜、專業且有幫助性，以促進用戶的職業發展和個人成長。"""
        else:  # Default to zh_CN
            system_role_prompt = """你是「职路领航员」，一位专业的职业发展顾问，在「职路」平台工作。「职路」是一家专注于职业咨询、技能培训和职业规划的综合平台。

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

重要：请使用简体中文回复，因为用户选择了简体中文作为偏好语言。

在与用户的互动中，保持谦逊、专业且有帮助性，以促进用户的职业发展和个人成长。"""

        history.insert(0, {"role": "system", "content": system_role_prompt})

        # Add interaction suggestions prompt based on user language
        if user_lang == 'en':
            interaction_prompt = """
Analyze the context and reply to the user's message following these guidelines:

【Reply Structure Requirements】
1. Main Content: Clearly and systematically respond to the user's questions, providing valuable insights and suggestions, preferably with practical examples or cases to help the user better understand.
2. Separator: Use this special string as a separator after the main content: <|------ Interaction Suggestions ------|>
3. Interaction Suggestions: Provide interaction suggestions in JSON format after the separator, including these three types of information:
   - questions_to_ai: Follow-up questions that the user might want to ask the AI (from the user's perspective and tone)
   - questions_to_user: Questions that the AI asks the user (from the AI's perspective and tone, to gather more information)
   - tools: Recommended platform tools to help the user solve specific problems

【When to Use Interaction Suggestions】
1. questions_to_ai: Provide questions from the user's perspective (must provide 3 questions)
   - Based on the current topic of discussion, predict related directions the user might want to explore further
   - Provide expansive questions to help the user explore broader related topics
   - Provide specific, practical, follow-up questions based on the current discussion
   - Use first person from the user's perspective ("How should I...", "What is...")

2. questions_to_user: Provide questions from the AI's perspective (must provide 1-3 questions)
   - When more information is needed to provide more accurate advice
   - When the user's needs or situation are not clear enough
   - Questions should help the AI better understand the user's specific situation and needs
   - Use first person from the AI's perspective ("Can you tell me...", "Do you want...")

3. Tool recommendations (tools): Recommend platform tools in the following situations
   - career_assessment: When the user needs to understand their career tendencies and ability characteristics
   - job_analysis: When the user needs detailed information, requirements, and development paths for specific positions
   - resume_optimization: When the user mentions resume writing or optimization needs
   - learning_path_gen: When the user seeks learning path recommendations for specific skills or positions, should carry parameters, such as:
     - learning_path_gen(Advanced Python Developer): Recommends learning path for Advanced Python Developer
     - learning_path_gen(Product Manager): Recommends learning path for Product Manager
     - learning_path_gen(UI Design): Recommends learning path for UI Design

【JSON Format Specification】
Strictly follow this schema format, ensuring correct JSON syntax:
```json
{
    "questions_to_ai": ["Specific user perspective question 1", "Specific user perspective question 2", "Specific user perspective question 3"],
    "questions_to_user": ["Specific AI perspective question 1", "Specific AI perspective question 2", "Specific AI perspective question 3"],
    "tools": ["Applicable tool 1", "Applicable tool 2", ...]
}
```

Note:
- Between the main content and interaction suggestions, use the correct separator
- In JSON, double quotes (") must be used instead of single quotes (')
- The questions_to_ai array must contain 3 questions, using the user's first person
- The questions_to_user array must contain 1-3 questions, using the AI's first person
- The tools array can be empty, or contain 1-4 recommended tools
- Array elements are separated by commas
- Properties need to be separated by commas
"""
        elif user_lang == 'zh_TW':
            interaction_prompt = """
分析上下文並回覆用戶消息，遵循以下指導原則：

【回覆結構要求】
1. 主要內容：清晰、有條理地回應用戶問題，提供有價值的見解和建議，最好能提供實際的示例或者案例，以幫助用戶更好地理解。
2. 分隔符：在主要內容結束後，使用該特殊字符串作為分隔符: <|------ 互動建議 ------|>
3. 互動建議：在分隔符後提供JSON格式的互動建議，包含以下三類信息：
   - questions_to_ai：用戶可能想問AI的後續問題（以用戶的視角和口吻提問）
   - questions_to_user：AI向用戶提出的問題（以AI的視角和口吻提問，用於獲取更多信息）
   - tools：推薦平台工具，幫助用戶解決特定問題

【互動建議的使用場景】
1. questions_to_ai：提供用戶視角的問題（必須提供3個問題）
   - 根據當前討論主題，預測用戶可能想深入了解的相關方向
   - 提供拓展性問題，幫助用戶探索更廣泛的相關主題
   - 提供具體的、實用的、基於當前討論的後續問題
   - 使用用戶的第一人稱（"我應該如何..."、"什麼是..."）

2. questions_to_user：提供AI視角的問題（必須提供1-3個問題）
   - 當需要更多信息來提供更準確的建議時
   - 當用戶的需求或情況不夠明確時
   - 提問應助於AI更好地理解用戶的具體情況和需求
   - 使用AI的第一人稱（"你能告訴我..."、"你希望..."）

3. 工具推薦(tools)：在以下情況推薦平台工具
   - career_assessment：當用戶需要了解自身職業傾向、能力特點
   - job_analysis：當用戶需要特定職位的詳細信息、要求、發展路徑
   - resume_optimization：當用戶提到簡歷撰寫或優化需求
   - learning_path_gen：當用戶尋求特定技能或職位的學習路徑推薦，應該攜帶參數，比如:
     - learning_path_gen(Python高級開發工程師)：推薦Python高級開發工程師的學習路徑
     - learning_path_gen(產品經理)：推薦產品經理的學習路徑
     - learning_path_gen(UI設計)：推薦UI設計的學習路徑

【JSON格式規範】
嚴格遵循以下schema格式，確保JSON語法正確：
```json
{
    "questions_to_ai": ["具體的用戶視角問題1", "具體的用戶視角問題2", "具體的用戶視角問題3"],
    "questions_to_user": ["具體的AI視角問題1", "具體的AI視角問題2", "具體的AI視角問題3"],
    "tools": ["適用工具1", "適用工具2", ...]
}
```

注意：
- 在主要內容和互動建議之間，要使用正確的分隔符
- JSON中必須使用雙引號(")而非單引號(')
- questions_to_ai數組必須包含3個問題，使用用戶第一人稱
- questions_to_user數組必須包含1-3個問題，使用AI第一人稱
- tools數組可為空，或包含1-4個推薦工具
- 數組元素之間用逗號分隔
- 各屬性之間需要逗號分隔
"""
        else:  # Default to zh_CN
            interaction_prompt = """
分析上下文并回复用户消息，遵循以下指导原则：

【回复结构要求】
1. 主要内容：清晰、有条理地回应用户问题，提供有价值的见解和建议，最好能提供实际的示例或者案例，以帮助用户更好地理解。
2. 分隔符：在主要内容结束后，使用该特殊字符串作为分隔符: <|------ 互动建议 ------|>
3. 互动建议：在分隔符后提供JSON格式的互动建议，包含以下三类信息：
   - questions_to_ai：用户可能想问AI的后续问题（以用户的视角和口吻提问）
   - questions_to_user：AI向用户提出的问题（以AI的视角和口吻提问，用于获取更多信息）
   - tools：推荐平台工具，帮助用户解决特定问题

【互动建议的使用场景】
1. questions_to_ai：提供用户视角的问题（必须提供3个问题）
   - 根据当前讨论主题，预测用户可能想深入了解的相关方向
   - 提供拓展性问题，帮助用户探索更广泛的相关主题
   - 提供具体的、实用的、基于当前讨论的后续问题
   - 使用用户的第一人称（"我应该如何..."、"什么是..."）

2. questions_to_user：提供AI视角的问题（必须提供1-3个问题）
   - 当需要更多信息来提供更准确的建议时
   - 当用户的需求或情况不够明确时
   - 提问应助于AI更好地理解用户的具体情况和需求
   - 使用AI的第一人称（"你能告诉我..."、"你希望..."）

3. 工具推荐(tools)：在以下情况推荐平台工具
   - career_assessment：当用户需要了解自身职业倾向、能力特点
   - job_analysis：当用户需要特定职位的详细信息、要求、发展路径
   - resume_optimization：当用户提到简历撰写或优化需求
   - learning_path_gen：当用户寻求特定技能或职位的学习路径推荐，应该携带参数，比如:
     - learning_path_gen(Python高级开发工程师)：推荐Python高级开发工程师的学习路径
     - learning_path_gen(产品经理)：推荐产品经理的学习路径
     - learning_path_gen(UI设计)：推荐UI设计的学习路径

【JSON格式规范】
严格遵循以下schema格式，确保JSON语法正确：
```json
{
    "questions_to_ai": ["具体的用户视角问题1", "具体的用户视角问题2", "具体的用户视角问题3"],
    "questions_to_user": ["具体的AI视角问题1", "具体的AI视角问题2", "具体的AI视角问题3"],
    "tools": ["适用工具1", "适用工具2", ...]
}
```

注意：
- 在主要内容和互动建议之间，要使用正确的分隔符
- JSON中必须使用双引号(")而非单引号(')
- questions_to_ai数组必须包含3个问题，使用用户第一人称
- questions_to_user数组必须包含1-3个问题，使用AI第一人称
- tools数组可为空，或包含1-4个推荐工具
- 数组元素之间用逗号分隔
- 各属性之间需要逗号分隔
"""

        history.insert(1, {"role": "system", "content": interaction_prompt})

        if chat_context:
            try:
                history.extend(chat_msgs_from_context(chat_context))
            except Exception as e:
                current_app.logger.error(f"处理聊天上下文失败: {str(e)}")
                # 继续执行，这不是致命错误

        # Add final reminder about interaction suggestions based on user language
        if user_lang == 'en':
            final_reminder = """About the 【Interaction Suggestions】 section:
0. Separator: Use this special string as a separator after the main content: <|------ Interaction Suggestions ------|>
1. questions_to_ai: Must provide 3 specific, context-relevant questions, expressed in the user's first person
2. questions_to_user: Must provide 1-3 questions to gather more information, expressed in the AI's first person
3. Tools recommendations:
   - Job seeking scenarios: Appropriately recommend career_assessment, job_analysis, resume_optimization
   - Skill learning scenarios: Prioritize recommending learning_path_gen
4. Ensure correct JSON format, all properties separated by commas"""
        elif user_lang == 'zh_TW':
            final_reminder = """關於【互動建議】部分:
0. 分隔符：在主要內容結束後，使用該特殊字符串作為分隔符: <|------ 互動建議 ------|>
1. questions_to_ai: 必須提供3個具體的、與上下文相關的問題，使用用戶第一人稱表述
2. questions_to_user: 必須提供1-3個問題，用於獲取更多信息，使用AI第一人稱表述
3. tools推薦:
   - 求職場景: 適當推薦career_assessment, job_analysis, resume_optimization
   - 技能學習場景: 優先推薦learning_path_gen
4. 確保JSON格式正確，所有屬性間使用逗號分隔"""
        else:  # Default to zh_CN
            final_reminder = """关于【互动建议】部分:
0. 分隔符：在主要内容结束后，使用该特殊字符串作为分隔符: <|------ 互动建议 ------|>
1. questions_to_ai: 必须提供3个具体的、与上下文相关的问题，使用用户第一人称表述
2. questions_to_user: 必须提供1-3个问题，用于获取更多信息，使用AI第一人称表述
3. tools推荐:
   - 求职场景: 适当推荐career_assessment, job_analysis, resume_optimization
   - 技能学习场景: 优先推荐learning_path_gen
4. 确保JSON格式正确，所有属性间使用逗号分隔"""

        history.append({"role": "system", "content": final_reminder})

        # 消费积分
        try:
            success, points_spent = consume_points_for_service(user_id, ServiceType.AI_CHAT.value, _("AI聊天"))
            if not success:
                return Response(json.dumps({"error": _("积分扣除失败，请稍后重试"), "points_required": True}),
                                status=402, mimetype='application/json')
        except Exception as e:
            current_app.logger.error(f"积分消费失败: {str(e)}")
            return Response(json.dumps({"error": _("积分消费失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # 准备AI响应消息记录
        ai_message = None
        try:
            ai_message = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session.id,
                sender_type='ai',
                content="",  # 将在流式响应完成后更新
                timestamp=time.time(),
                message_metadata=message_metadata,
            )
            db.session.add(ai_message)
            session.updated_at = time.time()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"创建AI消息记录失败: {str(e)}")
            return Response(json.dumps({"error": _("创建AI消息记录失败，请稍后重试")}),
                            status=500, mimetype='application/json')

        # 创建流式响应
        def generate():
            full_response = ""

            current_app.logger.debug(f"history: {history}, user_message: {user_message}")

            # 发送积分消耗信息
            yield f"data: {json.dumps({'points_spent': points_spent})}\n\n"

            # 调用LLM API并处理流式响应
            try:
                for chunk in chat_with_llm_stream(user_message, history=history, model="qwen-2.5-32b", max_tokens=4096, platform="siliconflow"):
                    if chunk:
                        full_response += chunk
                        yield f"data: {json.dumps({'text': chunk, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"
            except Exception as e:
                error_msg = f"AI响应生成失败: {str(e)}"
                current_app.logger.error(error_msg)
                # 向客户端发送错误信息
                yield f"data: {json.dumps({'error': _('获取AI响应时出现错误，请稍后重试'), 'session_id': session.id, 'message_id': ai_message.id})}\n\n"
                # 保存错误信息到AI消息
                try:
                    ai_message.content = _("[系统提示: 获取AI响应时出现错误]")
                    db.session.commit()
                except Exception as db_error:
                    current_app.logger.error(f"保存错误消息失败: {str(db_error)}")
                yield f"data: {json.dumps({'done': True, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"
                return

            # 流式响应结束后，更新AI消息内容
            try:
                ai_message.content = full_response
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"更新AI消息内容失败: {str(e)}")
                # 继续执行，不中断客户端连接

            current_app.logger.debug(f"ai_message: {ai_message.content}")

            # 发送完成信号
            yield f"data: {json.dumps({'done': True, 'session_id': session.id, 'message_id': ai_message.id})}\n\n"

        return Response(stream_with_context(generate()),
                        mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache',
                                'X-Accel-Buffering': 'no'})

    except Exception as e:
        # 捕获整个函数的所有未处理异常
        error_detail = traceback.format_exc()
        current_app.logger.error(f"聊天请求处理失败: {str(e)}\n{error_detail}")
        return Response(json.dumps({"error": _("处理请求时发生错误，请稍后重试")}),
                        status=500, mimetype='application/json')

def get_chat_history(session_id, max_messages=6):
    """获取聊天历史记录用于AI上下文"""
    try:
        messages = ChatMessage.query.filter_by(session_id=session_id) \
                                .order_by(desc(ChatMessage.timestamp)) \
                                .limit(max_messages).all()

        # 构造历史记录格式
        history = []
        for message in messages:
            role = "user" if message.sender_type == "user" else "assistant"
            if role == "assistant" and "------ 互动建议 ------" in message.content:
                message.content = message.content.split("------ 互动建议 ------")[0]

            history.append({"role": role, "content": message.content})

        history.reverse()
        return history

    except Exception as e:
        logging.error(f"获取聊天历史记录失败: {str(e)}")
        # 如果无法获取历史记录，返回空列表以便继续服务
        return []

def chat_msgs_from_context(chat_context):
    """从聊天上下文中提取消息"""
    try:
        ref_msgs = chat_context.get("ref_msgs", [])
        if ref_msgs:
            return ref_msgs
        else:
            user_lang = get_user_lang()
            roadmap_title = chat_context.get("roadmap_title", _("未知主题"))
            node_title = chat_context.get("node_title", _("未知节点"))
            node_path = chat_context.get("node_path", _("未知路径"))
            node_description = chat_context.get("node_description", _("暂无描述"))

            if user_lang == 'en':
                user_prompt = f"I'm learning a major topic: '{roadmap_title}', my current learning path is '{node_path}', please explain this topic to me: '{node_title}'"
            elif user_lang == 'zh_TW':
                user_prompt = f"我正在學習一個大的主題：「{roadmap_title}」，目前的學習路徑是「{node_path}」，請給我解釋一下這個主題：「{node_title}」"
            else:  # Default to zh_CN
                user_prompt = f"我正在学习一个大的主题：「{roadmap_title}」，目前的学习路径是「{node_path}」，请给我解释一下这个主题：「{node_title}」"

            return [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": f"{node_description}"}
            ]
    except Exception as e:
        logging.error(f"处理聊天上下文失败: {str(e)}")
        # 返回空列表以便继续服务
        return []
