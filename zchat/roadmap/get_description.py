import re
import openai
import os

system_prompt_template = """
用户正在学习一个大的topic：{topic}。
在思维导图中，用户已经学习了部分内容，现在需要更详细的学习。 请根据用户提供的思维导图路径topic/sub_topic/leaf_topic的关键词信息，尽可能完善地描述right most的topic的内容。
"""

user_prompt_template = """
思维导图的关键词路径：{topic_path}

请给出对最叶子topic的详细说明，确保用户能对这个内容有非常深刻的理解。适当的情况下，可以推荐书籍，论文等资料，让用户进一步了解相关内容。

结果用JSON输出，需符合以下的schema:
"""

output_schema = """
```json
{
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "叶子关键词"
        },
        "path": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "关键词路径"
        },
        "description": {
            "type": "string",
            "description": "对关键词的详细解释，使用户能够完整理解该内容"
        }
    },
    "required": [
        "title",
        "path",
        "description"
    ],
}
```
"""

def get_llm_response(topic, topic_path):
  client = openai.OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    # base_url="http://127.0.0.1:8080/v1",
  )
  response = client.chat.completions.create(
    model="qwen-2.5-32b",
    # model="mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit",
    messages=[
      {"role": "system", "content": system_prompt_template.format(topic=topic)},
      {"role": "user", "content": user_prompt_template.format(topic_path=topic_path) + output_schema},
    ],
    max_tokens=32768,
  )
  return response.choices[0].message.content

def parse_llm_response(response):
  # 定义正则表达式模式：匹配 ```json 和 ``` 之间的内容
  pattern = r'```json\n(.*?)\n```'

  # 查找所有匹配的代码块
  json_blocks = re.findall(pattern, response, re.DOTALL)

  return json_blocks

def description_from_topic_path(topic, topic_path):
  response = get_llm_response(topic, topic_path)
  json_blocks = parse_llm_response(response)
  description = json_blocks[0]

  return description


if __name__ == "__main__":
  topic = "UI/UX设计基础"
  topic_path = "前端工程师->设计系统->UI/UX设计基础"
  description = description_from_topic_path(topic, topic_path)
  print(description)
