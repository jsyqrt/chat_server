import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response, get_response_from_llm_stream

system_prompt_template = """
您是一位专业的教育内容开发专家，擅长将复杂概念分解为清晰、全面的解释。

用户想要了解主题「{topic}」是什么，包含什么，并按照思维导图进行系统性学习。用户已经掌握了思维导图中的上层概念，现在需要深入理解特定的叶子节点概念。

您的任务是：
1. 分析该思维导图路径 (topic → subtopic → leaf_topic): {topic_path}
2. 在「{topic_path}」的前提背景下，「{topic}」具体代表了什么，提供深入、全面的解释
3. 使用技术博客，杂志期刊文章，或微信公众号文章的风格，但不要提供任何链接

您的解释应当：
- 专业且准确：确保技术细节正确无误
- 深入且全面：覆盖该概念的各个重要方面
- 实用且可操作：包含实际应用指导
- 循序渐进：考虑用户已有的知识基础

请记住，您的解释将直接影响用户对该概念的理解深度和学习效果。
"""

# 使用双花括号 {{ }} 来转义JSON中的花括号，避免与format()方法冲突
user_prompt_template = """
## 思维导图路径
{topic_path}

## 目标概念
{topic}

如果是写一篇大的文章，那些路径就是各级标题，「{topic}」就是当前章节的标题，所以你的任务是写出当前章节的内容。

"""

output_style = """
请使用犀利准确的语言，不要使用冗长的句子，不要使用复杂的句子。使用markdown格式。
"""

json_schema = """
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

def get_llm_response(topic, topic_path):
  messages=[
    {"role": "system", "content": system_prompt_template.format(topic=topic, topic_path='->'.join(topic_path[:-1]))},
    {"role": "user", "content": user_prompt_template.format(topic=topic, topic_path='->'.join(topic_path[:-1]))},
    {"role": "user", "content": json_schema},
  ]
  print(messages)
  # 使用更大的token限制以获取更详细的描述
  response = get_response_from_llm(messages, "qwen-2.5-32b", 4096, platform='siliconflow')
#   response = get_response_from_llm(messages, "qwen-2.5-32b", 8192, platform='aliyun')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def description_from_topic_path(topic, topic_path):
  response = get_llm_response(topic, topic_path)
  json_blocks = parse_llm_response(response)
  if len(json_blocks) == 0:
    return None

  description = json_blocks[0]
  return description

def get_llm_response_stream(topic, topic_path):
    messages=[
        {"role": "system", "content": system_prompt_template.format(topic=topic, topic_path='->'.join(topic_path[:-1]))},
        {"role": "user", "content": user_prompt_template.format(topic=topic, topic_path='->'.join(topic_path[:-1]))},
        {"role": "user", "content": output_style},
    ]
    # Use the stream function from llm.py
    return get_response_from_llm_stream(
        messages,
        "qwen-2.5-32b",
        4096,
        platform='siliconflow'
    )

def description_from_topic_path_stream(topic, topic_path):
    """Stream the description for a topic path directly from the LLM"""
    return get_llm_response_stream(topic, topic_path)

if __name__ == "__main__":
  topic = "UI/UX设计基础"
  topic_path = "前端工程师->设计系统->UI/UX设计基础"
  description = description_from_topic_path(topic, topic_path)
  print(description)
