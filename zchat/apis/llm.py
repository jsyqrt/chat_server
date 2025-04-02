import openai
import os
import re
from typing import Dict, List, Tuple

# 模型名称映射：根据基础模型名和平台名，提供平台特定的模型名称
MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
    "qwen-2.5-32b": {
        "groq": "qwen-2.5-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwen2.5-32b-instruct",
        "siliconflow": "Qwen/Qwen2.5-32B-Instruct"
    },
    "qwen-qwq-32b": {
        "groq": "qwen-qwq-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwq-32b-preview",
        "siliconflow": "Qwen/QwQ-32B"
    },
    "deepseek-r1" : {
        "groq": "qwen-qwq-32b",
        "deepseek": "deepseek-chat",
        "aliyun": "qwq-32b-preview",
        "siliconflow": "deepseek-ai/DeepSeek-R1"
    }
}

def get_platform_model_name(base_model: str, platform: str) -> str:
    """根据基础模型名和平台名，获取平台特定的模型名称"""
    if base_model not in MODEL_MAPPINGS:
        raise ValueError(f"未知的基础模型: {base_model}")

    if platform not in MODEL_MAPPINGS[base_model]:
        raise ValueError(f"平台 {platform} 不支持模型 {base_model}")

    return MODEL_MAPPINGS[base_model][platform]

def get_api_url_and_key(platform="groq"):
  if platform == "groq":
    return "https://api.groq.com/openai/v1", os.getenv("GROQ_API_KEY")
  elif platform == "deepseek":
    return "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_API_KEY")
  elif platform == "aliyun":
    return "https://dashscope.aliyuncs.com/compatible-mode/v1", os.getenv("ALIYUN_API_KEY")
  elif platform == "siliconflow":
    return "https://api.siliconflow.cn/v1", os.getenv("SF_ZCHAT_API_KEY")
  else:
    raise ValueError(f"Unsupported platform: {platform}")

def get_response_from_llm(messages, model, max_tokens, platform="groq"):
  api_url, api_key = get_api_url_and_key(platform)
  platform_model = get_platform_model_name(model, platform)
  client = openai.OpenAI(
    base_url=api_url,
    api_key=api_key,
    timeout=1200,
    # max_retries=3,
  )
  response = client.chat.completions.create(
    model=platform_model,
    messages=messages,
    max_tokens=max_tokens,
    temperature=0,
  )
  return response.choices[0].message.content

def get_response_from_llm_stream(messages, model, max_tokens, platform="groq"):
  api_url, api_key = get_api_url_and_key(platform)
  platform_model = get_platform_model_name(model, platform)
  client = openai.OpenAI(
    base_url=api_url,
    api_key=api_key,
  )
  response = client.chat.completions.create(
    model=platform_model,
    messages=messages,
    max_tokens=max_tokens,
    # temperature=0,
    stream=True,
  )
  for chunk in response:
    if chunk.choices[0].delta.content is not None:
      yield chunk.choices[0].delta.content

def chat_with_llm_stream(message, history, model, max_tokens, platform="groq"):
  messages = [{
    "role": "system",
    "content": """你是「职路领航员」，一位专业的职业发展顾问，在「职路」平台工作。「职路」是一家专注于职业咨询、技能培训和职业规划的综合平台。

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
  }]
  messages.extend(history)
  messages.append({"role": "system", "content": """
分析上下文并回复用户消息，遵循以下指导原则：

【回复结构要求】
1. 主要内容：清晰、有条理地回应用户问题，提供有价值的见解和建议
2. 分隔符：在主要内容结束后，使用"---"作为分隔符
3. 互动建议：在分隔符后提供JSON格式的互动建议，包含以下两类信息：
   - questions：3个相关后续问题，帮助用户深入探讨话题
   - tools：推荐平台工具，在适当情况下引导用户使用

【互动建议的使用场景】
1. 后续问题(questions)：
   - 当解释复杂概念后，提供相关的深入问题
   - 当用户可能需要更多信息时，提供引导性问题
   - 当话题有多个相关方向可探讨时，提供拓展性问题
   - 问题应简洁明了，直接相关，有思考价值

2. 工具推荐(tools)：在以下情况推荐平台工具
   - career_assessment：当用户需要了解自身职业倾向、能力特点
   - job_analysis：当用户需要特定职位的详细信息、要求、发展路径
   - resume_optimization：当用户提到简历撰写或优化需求
   - learning_path_gen：当用户寻求特定技能或职位的学习路径

【JSON格式规范】
严格遵循以下schema格式，确保JSON语法正确：
```json
{
    "questions": ["问题1", "问题2", "问题3"],
    "tools": ["tool1", "tool2", ...]
}
```

注意：
- JSON中必须使用双引号(")而非单引号(')
- questions数组必须包含3个问题
- tools数组可为空，或包含1-4个推荐工具
- 数组元素之间用逗号分隔
- "questions"和"tools"之间需要逗号分隔
"""})
  messages.append({"role": "user", "content": message})
  return get_response_from_llm_stream(messages, model, max_tokens, platform)

def get_json_blocks_from_llm_response(response):
  """从LLM响应中提取JSON代码块"""
  # 定义正则表达式模式：匹配 ```json 和 ``` 之间的内容
  pattern = r'```json\n(.*?)\n```'

  # 查找所有匹配的代码块
  json_blocks = re.findall(pattern, response, re.DOTALL)

  return json_blocks

def get_html_blocks_from_llm_response(response):
  """从LLM响应中提取HTML代码块"""
  # 定义正则表达式模式：匹配 ```html 和 ``` 之间的内容
  pattern = r'```html\n(.*?)\n```'

  # 查找所有匹配的代码块
  html_blocks = re.findall(pattern, response, re.DOTALL)

  return html_blocks
