import openai
import os
import re

def get_api_url_and_key(platform="groq"):
  if platform == "groq":
    return "https://api.groq.com/openai/v1", os.getenv("GROQ_API_KEY")
  elif platform == "deepseek":
    return "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_API_KEY")
  elif platform == "openai":
    return "https://api.openai.com/v1", os.getenv("OPENAI_API_KEY")
  else:
    raise ValueError(f"Unsupported platform: {platform}")

def get_response_from_llm(messages, model, max_tokens, platform="groq"):
  api_url, api_key = get_api_url_and_key(platform)
  client = openai.OpenAI(
    base_url=api_url,
    api_key=api_key,
  )
  response = client.chat.completions.create(
    model=model,
    messages=messages,
    max_tokens=max_tokens,
  )
  return response.choices[0].message.content

def get_json_blocks_from_llm_response(response):
  # 定义正则表达式模式：匹配 ```json 和 ``` 之间的内容
  pattern = r'```json\n(.*?)\n```'

  # 查找所有匹配的代码块
  json_blocks = re.findall(pattern, response, re.DOTALL)

  return json_blocks
