import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response, get_response_from_llm_stream

from flask import current_app

# Define writing styles
# English writing styles
ENGLISH_WRITING_STYLES = {
    "feynman": "Richard Feynman: Known for simple, intuitive explanations with vivid metaphors, conversational tone, and childlike curiosity",
    "graham": "Paul Graham: Clear writing with philosophical depth, personal experiences, and well-structured short paragraphs building to profound points",
    "musk": "Elon Musk: Direct, bold and visionary, using technical terms while focusing on future possibilities with concise, impactful language",
    "trump": "Donald Trump: Simple vocabulary with short sentences, repetition of key points, confident and direct, occasionally hyperbolic",
    "einstein": "Albert Einstein: Thoughtful approach combining complex concepts with everyday metaphors, balancing philosophical and scientific perspectives",
    "twain": "Mark Twain: Humorous and witty, masterful use of satire, vivid language, relatable storytelling with strong narrative flow",
    "hemingway": "Ernest Hemingway: Concise and powerful, short sentences, direct approach to subjects, minimal decoration or embellishment",
    "jobs": "Steve Jobs: Passionate and visionary, emphasizing simplicity and elegance, masterful storytelling, inspirational tone, creatively connecting technology with human values",
    "linus": "Linus Torvalds: Direct and frank, technically precise, focused on practicality and efficiency, straightforward with occasional humor or sharp criticism, emphasis on quality and technical merit"
}

# Chinese writing styles
CHINESE_WRITING_STYLES = {
    "feynman": "理查德·费曼 (Richard Feynman): 擅长用简单直观的语言和比喻解释复杂概念，对话式、亲切且充满好奇心",
    "graham": "保罗·格雷厄姆 (Paul Graham): 结合个人经验与哲学思考，文笔清晰而富有洞见，擅长用简短段落构建深刻论点",
    "musk": "埃隆·马斯克 (Elon Musk): 直接、大胆且有远见，经常使用技术术语并关注未来可能性，语言简洁有力",
    "trump": "唐纳德·特朗普 (Donald Trump): 使用简单词汇和短句，重复关键点，自信且直接，偶尔夸张",
    "luxun": "鲁迅: 犀利而深刻，善于讽刺与批判，文字凝练有力，寓意深远",
    "einstein": "阿尔伯特·爱因斯坦 (Albert Einstein): 思考性强，将复杂概念与日常比喻结合，哲学性与科学性并重",
    "twain": "马克·吐温 (Mark Twain): 幽默诙谐，善用讽刺，语言生动接地气，故事性强",
    "hemingway": "欧内斯特·海明威 (Ernest Hemingway): 简洁有力，短句为主，直接切入主题，避免过多修饰",
    "jobs": "史蒂夫·乔布斯 (Steve Jobs): 充满激情与远见，注重简洁优雅，善于讲故事，富有鼓舞性，创造性地将复杂技术与人文价值联系起来",
    "linus": "莱纳斯·托瓦兹 (Linus Torvalds): 直接坦率，技术精确，注重实用性和效率，不拐弯抹角，偶尔使用幽默或尖锐批评，关注代码质量与技术优势",
    "liao": "李敖: 锋利犀利，知识渊博，挑战权威，善用讽刺和调侃，语言直接不留情面，引经据典且充满挑衅性的智慧",
    "tseng": "曾仕强: 循循善诱，引用古典智慧，平易近人，娓娓道来，善于用故事阐释深刻道理，充满儒家思想与传统智慧",
    "liang": "梁宏达: 口语化、生动活泼，充满个人情感色彩，直言不讳，有强烈的节奏感，富有戏剧性，时而幽默时而激昂"
}

# Common styles available in both languages
COMMON_STYLES = ["feynman", "graham", "musk", "trump", "einstein", "twain", "hemingway", "jobs", "linus"]

# Chinese-only styles
CHINESE_ONLY_STYLES = ["luxun", "liao", "tseng", "liang"]

# Chinese system prompt
system_prompt_template_zh = """
您是一位天才级的教育者和解释者，擅长将复杂概念转化为生动、引人入胜且易于理解的解释。

您需要以{style_name}的风格来写作。{style_description}

用户想要了解主题「{topic}」，并希望获得既深入又引人入胜的解释。用户已经掌握了思维导图中的上层概念，现在需要深入理解特定的概念。

您的任务是：
1. 分析该思维导图路径 (topic → subtopic → leaf_topic): {topic_path}
2. 以一种引人入胜、对话式的方式解释「{topic}」，就像您正在与一位聪明的朋友交谈
3. 使用富有{style_name}风格的语言 - 既有深度又易于理解
4. 在解释中穿插恰当的比喻、故事和实例，使抽象概念变得具体
5. 平衡非正式的解释与必要的形式化定义，先给直觉性理解，再给精确定义
6. 给出用户有可能想要进一步提问的3个问题，用于下一步与AI交互对话的提示词
7. 创建5道测试题（单选或多选题, 至少包含1道多选题），风格同样应当生动有趣

您的解释应当：
- 富有个人风格：就像{style_name}在交谈，而非教科书的冰冷语言
- 从具体到抽象：先给出具体例子和比喻，再逐步引入抽象概念
- 引人入胜：开场就能抓住读者的注意力，激发继续阅读的欲望
- 具有连贯的叙事：而不是零散的知识点堆砌
- 包含个人见解：提供独到的视角和思考角度，就像{style_name}会做的那样
- 使用生动的比喻：帮助读者建立直观的理解模型

此外，请注意以下信息：
- 「{topic}」的兄弟节点有：{siblings}，这些节点将在其他章节中详细解释
- 「{topic}」的子节点有：{children}，这些节点将在后续章节中详细解释
- 请专注于解释「{topic}」本身的内容，避免过多涉及其他节点将会详细解释的内容

请记住，优秀的解释不只是传递正确的信息，还能激发读者的思考和学习兴趣。
"""

# English system prompt
system_prompt_template_en = """
You are a brilliant educator and explainer, skilled at transforming complex concepts into vivid, engaging, and easily understandable explanations.

You need to write in the style of {style_name}. {style_description}

The user wants to understand the topic "{topic}" and desires an explanation that is both deep and engaging. The user has already mastered the higher-level concepts in the mind map and now needs to deeply understand this specific concept.

Your task is to:
1. Analyze the mind map path (topic → subtopic → leaf_topic): {topic_path}
2. Explain "{topic}" in an engaging, conversational manner, as if you're talking to a smart friend
3. Use language with the personal flair of {style_name} - both insightful and accessible
4. Weave appropriate metaphors, stories, and examples into your explanation to make abstract concepts concrete
5. Balance informal explanation with necessary formal definitions - intuitive understanding first, precise definitions second
6. Provide 3 questions the user might want to ask further, to be used as prompts for the next step in AI interactive dialogue
7. Create 5 test questions (single or multiple choice, at least 1 multiple choice) that are also vibrant and engaging

Your explanation should be:
- Personally styled: like {style_name} talking, not the cold language of a textbook
- Concrete to abstract: start with specific examples and metaphors, then gradually introduce abstract concepts
- Engaging: grab the reader's attention from the beginning and spark the desire to keep reading
- Narratively coherent: not just a pile of disconnected knowledge points
- Insightful: provide unique perspectives and angles of thinking, as {style_name} would
- Rich with vivid metaphors: help readers build intuitive mental models

Additionally, please note the following information:
- The sibling nodes of "{topic}" include: {siblings}, which will be explained in detail in other sections
- The child nodes of "{topic}" include: {children}, which will be explained in detail in subsequent sections
- Please focus on explaining "{topic}" itself. Avoid excessive coverage of content that will be explained in detail in other nodes

Remember, great explanations don't just convey correct information; they inspire thinking and curiosity in the reader.
"""

# Chinese user prompt
user_prompt_template_zh = """
## 思维导图路径
{topic_path}

## 目标概念
{topic}

## 兄弟节点
{siblings}

## 子节点
{children}

请为「{topic}」创作一篇深入浅出的解释，风格应像{style_name} - {style_description}。既有思想深度又易于理解，富有个人风格的语言，使用恰当的比喻和例子，平衡非正式的解释与必要的形式化定义。就像您在与一位聪明的朋友交谈，而不是在写一篇学术论文。

兄弟节点和子节点会在其他章节中详细解释，所以请专注于当前节点的内容，避免过多涉及将在其他章节详细讲解的内容。

"""

# English user prompt
user_prompt_template_en = """
## Mind Map Path
{topic_path}

## Target Concept
{topic}

## Sibling Nodes
{siblings}

## Child Nodes
{children}

Please create an explanation for "{topic}" that's both deep and accessible, in the style of {style_name} - {style_description}. It should be intellectually rich yet easy to understand, with personal flair in your language, appropriate metaphors and examples, and a balance of informal explanation with necessary formal definitions. Write as if you're talking to a smart friend, not writing an academic paper.

The sibling nodes and child nodes will be explained in detail in other sections, so please focus on the content of the current node, avoiding excessive coverage of content that will be explained in other sections.

"""

# Chinese output style
output_style_zh = """
请使用生动、亲切且富有{style_name}风格的语言，就像在与朋友交谈一样。避免过于正式或学术化的表达，转而使用引人入胜的叙事、生动的比喻和具体的例子。使用markdown格式。

在解释的最后，给出用户有可能想要进一步提问的3个问题，以及5道测试题（可以是单选题或多选题）。
正文与问题及测试题之间用<|------ 互动建议 ------|>隔开。这部分只包含一个json对象，不要包含其他内容。
这三个问题要与当前解释的内容紧密相关，要站在用户的角度，考虑用户可能的疑问。
测试题用于测试用户对知识的掌握情况，每道题包含题目内容、选项、正确答案和解析。
问题和测试题需要用json格式输出，严格遵循以下schema，注意在json中使用正确的引号。
```json
{{
    "questions": ["用户可能想要了解的问题1", "用户可能想要了解的问题2", "用户可能想要了解的问题3"],
    "quizzes": [
        {{
            "question": "测试题1的题目内容",
            "options": ["测试题1的选项A", "测试题1的选项B", "测试题1的选项C", "测试题1的选项D"],
            "answer": [0],  // 答案为选项的索引，从0开始计数，单选题为一个数字，多选题为数组
            "explanation": "测试题1的解析说明为什么这是正确答案"
        }},
        // 其他4道测试题
    ]
}}
```

必须用中文回答。

开始你的解释。
"""

# English output style
output_style_en = """
Please use vivid, friendly, and personally styled language in the style of {style_name}, as if you're conversing with a friend. Avoid overly formal or academic expressions, and instead use engaging narratives, vivid metaphors, and concrete examples. Use markdown format.

At the end of your explanation, provide 3 questions that the user might want to ask further, and 5 test questions (single or multiple choice).
Separate the main text from the questions and test questions with <|------ Interaction Suggestions ------|>. This section should only contain one JSON object, without any other content.
These three questions should be closely related to the current explanation, from the user's perspective, considering possible user inquiries.
The test questions aim to assess the user's understanding of the topic, each including the question content, options, correct answer(s), and explanation.
The questions and test questions need to be output in JSON format, strictly following this schema, and using correct quotation marks in the JSON.
```json
{{
    "questions": ["Question 1 that user may ask", "Question 2 that user may ask", "Question 3 that user may ask"],
    "quizzes": [
        {{
            "question": "Question content of quiz question 1",
            "options": ["Option A of quiz question 1", "Option B of quiz question 1", "Option C of quiz question 1", "Option D of quiz question 1"],
            "answer": [0],  // Answer as index of options, starting from 0, single number for single choice, array for multiple choice
            "explanation": "Explanation of why this is the correct answer of quiz question 1"
        }},
        // Other 4 quiz questions
    ]
}}
```

Must respond in English.

Begin your explanation.
"""

# Chinese JSON schema
json_schema_zh = """
请以JSON格式输出，严格遵循以下schema：

```json
{{
    "type": "object",
    "properties": {{
        "title": {{
            "type": "string",
            "description": "叶子概念的标题"
        }},
        "path": {{
            "type": "array",
            "items": {{
                "type": "string"
            }},
            "description": "从根节点到叶子节点的完整路径"
        }},
        "description": {{
            "type": "string",
            "description": "详细解释，包含定义、原理、应用等全面内容, markdown格式"
        }}
    }},
    "required": [
        "title",
        "path",
        "description",
    ]
}}
```

请确保输出的JSON格式正确，可以直接被解析。不要添加额外的解释或注释。
"""

# English JSON schema
json_schema_en = """
Please output in JSON format, strictly following this schema:

```json
{{
    "type": "object",
    "properties": {{
        "title": {{
            "type": "string",
            "description": "Title of the leaf concept"
        }},
        "path": {{
            "type": "array",
            "items": {{
                "type": "string"
            }},
            "description": "Complete path from root node to leaf node"
        }},
        "description": {{
            "type": "string",
            "description": "Detailed explanation including definition, principles, applications, etc., in markdown format"
        }}
    }},
    "required": [
        "title",
        "path",
        "description",
    ]
}}
```

Ensure the output JSON format is correct and can be parsed directly. Do not add additional explanations or comments.
"""

def get_style_info(style, lang):
    """Get style name and description based on style code and language"""
    # Default to Feynman style
    if not style:
        style = "feynman"

    style = style.lower()

    # Determine which style dictionary to use
    if lang == 'en':
        # Don't allow Chinese-only styles for English content
        if style in CHINESE_ONLY_STYLES:
            style = "feynman"

        if style not in ENGLISH_WRITING_STYLES:
            style = "feynman"

        style_dict = ENGLISH_WRITING_STYLES
    else:  # Chinese
        if style not in CHINESE_WRITING_STYLES:
            style = "feynman"

        style_dict = CHINESE_WRITING_STYLES

    # Split into name and description
    style_parts = style_dict[style].split(": ", 1)
    style_name = style_parts[0]
    style_description = style_parts[1] if len(style_parts) > 1 else ""

    return style_name, style_description

def get_prompts_by_language(lang, style=None):
    """Get the appropriate prompts based on the user's language and style"""
    style_name, style_description = get_style_info(style, lang)

    if lang == 'en':
        return {
            'system_prompt': system_prompt_template_en.format(
                style_name=style_name,
                style_description=style_description,
                topic_path="{topic_path}",
                topic="{topic}",
                siblings="{siblings}",
                children="{children}"
            ),
            'user_prompt': user_prompt_template_en.format(
                style_name=style_name,
                style_description=style_description,
                topic_path="{topic_path}",
                topic="{topic}",
                siblings="{siblings}",
                children="{children}"
            ),
            'output_style': output_style_en.format(
                style_name=style_name
            ),
            'json_schema': json_schema_en
        }
    else:  # default to Chinese (zh_CN)
        return {
            'system_prompt': system_prompt_template_zh.format(
                style_name=style_name,
                style_description=style_description,
                topic_path="{topic_path}",
                topic="{topic}",
                siblings="{siblings}",
                children="{children}"
            ),
            'user_prompt': user_prompt_template_zh.format(
                style_name=style_name,
                style_description=style_description,
                topic_path="{topic_path}",
                topic="{topic}",
                siblings="{siblings}",
                children="{children}"
            ),
            'output_style': output_style_zh.format(
                style_name=style_name
            ),
            'json_schema': json_schema_zh
        }

def get_llm_response(topic, topic_path, siblings=None, children=None, lang='zh_CN', style=None):
  prompts = get_prompts_by_language(lang, style)
  siblings_str = "、".join(siblings) if siblings else "无"
  children_str = "、".join(children) if children else "无"
  topic_path_str = '->'.join(topic_path[:-1])

  messages=[
    {"role": "system", "content": prompts['system_prompt'].format(
        topic=topic,
        topic_path=topic_path_str,
        siblings=siblings_str,
        children=children_str
    )},
    {"role": "user", "content": prompts['user_prompt'].format(
        topic=topic,
        topic_path=topic_path_str,
        siblings=siblings_str,
        children=children_str
    )},
    {"role": "user", "content": prompts['json_schema']},
  ]
  current_app.logger.debug(f"get_llm_response messages: {messages}")
  # 使用更大的token限制以获取更详细的描述
  response = get_response_from_llm(messages, "qwen-2.5-32b", 4096, platform='siliconflow')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def description_from_topic_path(topic, topic_path, siblings=None, children=None, lang='zh_CN', style=None):
  response = get_llm_response(topic, topic_path, siblings, children, lang, style)
  json_blocks = parse_llm_response(response)
  if len(json_blocks) == 0:
    return None

  description = json_blocks[0]
  return description

def get_llm_response_stream(topic, topic_path, siblings=None, children=None, lang='zh_CN', style=None):
    prompts = get_prompts_by_language(lang, style)
    siblings_str = "、".join(siblings) if siblings else "无"
    children_str = "、".join(children) if children else "无"
    topic_path_str = '->'.join(topic_path[:-1])

    messages=[
        {"role": "system", "content": prompts['system_prompt'].format(
            topic=topic,
            topic_path=topic_path_str,
            siblings=siblings_str,
            children=children_str
        )},
        {"role": "user", "content": prompts['user_prompt'].format(
            topic=topic,
            topic_path=topic_path_str,
            siblings=siblings_str,
            children=children_str
        )},
        {"role": "user", "content": prompts['output_style']},
    ]
    current_app.logger.debug(f"get_llm_response_stream messages: {messages}")
    # Use the stream function from llm.py
    return get_response_from_llm_stream(messages, "qwen-2.5-32b", 4096, platform='siliconflow')

def description_from_topic_path_stream(topic, topic_path, siblings=None, children=None, lang='zh_CN', style=None):
    """Stream the description for a topic path directly from the LLM"""
    return get_llm_response_stream(topic, topic_path, siblings, children, lang, style)

if __name__ == "__main__":
  topic = "UI/UX设计基础"
  topic_path = "前端工程师->设计系统->UI/UX设计基础"
  siblings = ["响应式设计", "设计系统组件"]
  children = ["色彩理论", "排版基础", "交互设计原则"]
  description = description_from_topic_path(topic, topic_path, siblings, children)
  print(description)
