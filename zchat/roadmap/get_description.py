import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response, get_response_from_llm_stream

from flask import current_app

# Chinese system prompt
system_prompt_template_zh = """
您是一位专业的教育内容开发专家，擅长将复杂概念分解为清晰、全面的解释。

用户想要了解主题「{topic}」是什么，包含什么，并按照思维导图进行系统性学习。用户已经掌握了思维导图中的上层概念，现在需要深入理解特定的叶子节点概念。

您的任务是：
1. 分析该思维导图路径 (topic → subtopic → leaf_topic): {topic_path}
2. 在「{topic_path}」的前提背景下，「{topic}」具体代表了什么，提供深入、全面的解释
3. 使用大部头教科书，学术论文，或技术博客的风格，但不要提供任何链接。需要详细，全面，深入，完整的解释和描述。
4. 给出用户有可能想要进一步提问的3个问题，用于下一步与AI交互对话的提示词
5. 创建5道测试题（单选或多选题, 至少包含1道多选题），用于测试用户对知识的掌握情况，每道题包含题目内容、选项、正确答案和解析

您的解释应当：
- 专业且准确：确保技术细节正确无误
- 深入且全面：覆盖该概念的各个重要方面
- 实用且可操作：包含实际应用指导
- 循序渐进：考虑用户已有的知识基础
- 给出示例：最好给出一些实际的例子，包括使用场景，具体操作，应用案例等等，帮助用户理解

此外，请注意以下信息：
- 「{topic}」的兄弟节点有：{siblings}，这些节点将在其他章节中详细解释
- 「{topic}」的子节点有：{children}，这些节点将在后续章节中详细解释
- 请专注于解释「{topic}」本身的内容，避免过多涉及其他节点将会详细解释的内容

请记住，您的解释将直接影响用户对该概念的理解深度和学习效果。
"""

# English system prompt
system_prompt_template_en = """
You are a professional educational content developer, skilled at breaking down complex concepts into clear, comprehensive explanations.

The user wants to understand what the topic "{topic}" is, what it encompasses, and learn it systematically according to a mind map. The user has already mastered the higher-level concepts in the mind map and now needs to deeply understand this specific leaf node concept.

Your task is to:
1. Analyze the mind map path (topic → subtopic → leaf_topic): {topic_path}
2. Within the context of "{topic_path}", explain what "{topic}" specifically represents, providing a deep, comprehensive explanation
3. Use the style of textbooks, academic papers, or technical blogs, but do not provide any links. The explanation needs to be detailed, comprehensive, in-depth, and complete.
4. Provide 3 questions the user might want to ask further, to be used as prompts for the next step in AI interactive dialogue
5. Create 5 test questions (single or multiple choice, at least 1 multiple choice) to assess the user's understanding of the topic, each including the question content, options, correct answer(s), and explanation

Your explanation should be:
- Professional and accurate: ensure technical details are correct
- Deep and comprehensive: cover all important aspects of the concept
- Practical and actionable: include practical application guidance
- Progressive: consider the user's existing knowledge base
- Provide examples: ideally include practical examples, including usage scenarios, specific operations, application cases, etc., to help users understand

Additionally, please note the following information:
- The sibling nodes of "{topic}" include: {siblings}, which will be explained in detail in other sections
- The child nodes of "{topic}" include: {children}, which will be explained in detail in subsequent sections
- Please focus on explaining "{topic}" itself. Avoid excessive coverage of content that will be explained in detail in other nodes

Please remember that your explanation will directly impact the depth of the user's understanding and learning effectiveness.
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

如果是写一篇大的文章，那些路径就是各级标题，「{topic}」就是当前章节的标题，所以你的任务是写出当前章节的内容。兄弟节点和子节点会在其他章节中详细解释，所以请专注于当前节点的内容，避免过多涉及将在其他章节详细讲解的内容。注意确保你的语言风格和输出内容的质量符合要求。

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

If this were a large article, the path would represent different levels of headings, and "{topic}" would be the title of the current section. So your task is to write the content of this current section. The sibling nodes and child nodes will be explained in detail in other sections, so please focus on the content of the current node, avoiding excessive coverage of content that will be explained in other sections. Make sure your language style and output quality meet the requirements.

"""

# Chinese output style
output_style_zh = """
请使用犀利准确的语言，不要使用冗长的句子，不要使用复杂的句子。使用markdown格式。

在解释的最后，给出用户有可能想要进一步提问的3个问题，以及5道测试题（可以是单选题或多选题）。
正文与问题及测试题之间用<|------ 互动建议 ------|>隔开。这部分只包含一个json对象，不要包含其他内容。
这三个问题要与当前解释的内容紧密相关，要站在用户的角度，考虑用户可能的疑问。
测试题用于测试用户对知识的掌握情况，每道题包含题目内容、选项、正确答案和解析。
问题和测试题需要用json格式输出，严格遵循以下schema，注意在json中使用正确的引号。
```json
{
    "questions": ["用户可能想要了解的问题1", "用户可能想要了解的问题2", "用户可能想要了解的问题3"],
    "quizzes": [
        {
            "question": "测试题1的题目内容",
            "options": ["测试题1的选项A", "测试题1的选项B", "测试题1的选项C", "测试题1的选项D"],
            "answer": [0],  // 答案为选项的索引，从0开始计数，单选题为一个数字，多选题为数组
            "explanation": "测试题1的解析说明为什么这是正确答案"
        },
        // 其他4道测试题
    ]
}
```

必须用中文回答。

开始你的解释。
"""

# English output style
output_style_en = """
Please use precise and accurate language, avoiding long or complex sentences. Use markdown format.

At the end of your explanation, provide 3 questions that the user might want to ask further, and 5 test questions (single or multiple choice).
Separate the main text from the questions and test questions with <|------ Interaction Suggestions ------|>. This section should only contain one JSON object, without any other content.
These three questions should be closely related to the current explanation, from the user's perspective, considering possible user inquiries.
The test questions aim to assess the user's understanding of the topic, each including the question content, options, correct answer(s), and explanation.
The questions and test questions need to be output in JSON format, strictly following this schema, and using correct quotation marks in the JSON.
```json
{
    "questions": ["Question 1 that user may ask", "Question 2 that user may ask", "Question 3 that user may ask"],
    "quizzes": [
        {
            "question": "Question content of quiz question 1",
            "options": ["Option A of quiz question 1", "Option B of quiz question 1", "Option C of quiz question 1", "Option D of quiz question 1"],
            "answer": [0],  // Answer as index of options, starting from 0, single number for single choice, array for multiple choice
            "explanation": "Explanation of why this is the correct answer of quiz question 1"
        },
        // Other 4 quiz questions
    ]
}
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

def get_prompts_by_language(lang):
    """Get the appropriate prompts based on the user's language"""
    if lang == 'en':
        return {
            'system_prompt': system_prompt_template_en,
            'user_prompt': user_prompt_template_en,
            'output_style': output_style_en,
            'json_schema': json_schema_en
        }
    else:  # default to Chinese (zh_CN)
        return {
            'system_prompt': system_prompt_template_zh,
            'user_prompt': user_prompt_template_zh,
            'output_style': output_style_zh,
            'json_schema': json_schema_zh
        }

def get_llm_response(topic, topic_path, siblings=None, children=None, lang='zh_CN'):
  prompts = get_prompts_by_language(lang)
  siblings_str = "、".join(siblings) if siblings else "无"
  children_str = "、".join(children) if children else "无"

  messages=[
    {"role": "system", "content": prompts['system_prompt'].format(
        topic=topic,
        topic_path='->'.join(topic_path[:-1]),
        siblings=siblings_str,
        children=children_str
    )},
    {"role": "user", "content": prompts['user_prompt'].format(
        topic=topic,
        topic_path='->'.join(topic_path[:-1]),
        siblings=siblings_str,
        children=children_str
    )},
    {"role": "user", "content": prompts['json_schema']},
  ]
  current_app.logger.debug(f"get_llm_response messages: {messages}")
  # 使用更大的token限制以获取更详细的描述
  response = get_response_from_llm(messages, "qwen-2.5-32b", 4096, platform='siliconflow')
#   response = get_response_from_llm(messages, "qwen-2.5-32b", 8192, platform='aliyun')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def description_from_topic_path(topic, topic_path, siblings=None, children=None, lang='zh_CN'):
  response = get_llm_response(topic, topic_path, siblings, children, lang)
  json_blocks = parse_llm_response(response)
  if len(json_blocks) == 0:
    return None

  description = json_blocks[0]
  return description

def get_llm_response_stream(topic, topic_path, siblings=None, children=None, lang='zh_CN'):
    prompts = get_prompts_by_language(lang)
    siblings_str = "、".join(siblings) if siblings else "无"
    children_str = "、".join(children) if children else "无"

    messages=[
        {"role": "system", "content": prompts['system_prompt'].format(
            topic=topic,
            topic_path='->'.join(topic_path[:-1]),
            siblings=siblings_str,
            children=children_str
        )},
        {"role": "user", "content": prompts['user_prompt'].format(
            topic=topic,
            topic_path='->'.join(topic_path[:-1]),
            siblings=siblings_str,
            children=children_str
        )},
        {"role": "user", "content": prompts['output_style']},
    ]
    current_app.logger.debug(f"get_llm_response_stream messages: {messages}")
    # Use the stream function from llm.py
    return get_response_from_llm_stream(
        messages,
        "qwen-2.5-32b",
        4096,
        platform='siliconflow'
    )

def description_from_topic_path_stream(topic, topic_path, siblings=None, children=None, lang='zh_CN'):
    """Stream the description for a topic path directly from the LLM"""
    return get_llm_response_stream(topic, topic_path, siblings, children, lang)

if __name__ == "__main__":
  topic = "UI/UX设计基础"
  topic_path = "前端工程师->设计系统->UI/UX设计基础"
  siblings = ["响应式设计", "设计系统组件"]
  children = ["色彩理论", "排版基础", "交互设计原则"]
  description = description_from_topic_path(topic, topic_path, siblings, children)
  print(description)
