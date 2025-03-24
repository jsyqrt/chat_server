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
