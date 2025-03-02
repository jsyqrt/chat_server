import re
import openai
import os

system_prompt_template = """
请分析提供的topic，为用户规划一条学习路径。学习路径需详细分析topic，将学习目标分解为10-15个主要主题或知识点，每个主题包含5-10个子主题或知识点，形成前后依赖的学习顺序。

最后，以思维导图的形式表示学习路径，并用JSON格式输出思维导图结构。

"""

user_prompt= """
学习路径的JSON，使用思维导图表示，用JSON输出，需要符合以下JSON Schema：
```json
{
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "节点标题"
        },
        "children": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/node"
            },
            "description": "子节点列表"
        }
    },
    "required": [
        "title",
        "children"
    ],
    "definitions": {
        "node": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "节点标题"
                },
                "children": {
                    "type": "array",
                    "items": {
                        "$ref": "#/definitions/node"
                    },
                    "description": "子节点列表"
                }
            },
            "required": [
                "title"
            ]
        }
    }
}
```
确保输出严格遵循上述JSON Schema，确保数据完整性和一致性。

"""

topic_prompt_template = """
topic信息：
```text
{topic}
```
"""

def get_llm_response(topic):
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
      {"role": "user", "content": user_prompt + topic_prompt_template.format(topic=topic)},
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

def mindmap_from_topic(topic):
  response = get_llm_response(topic)
  json_blocks = parse_llm_response(response)
  mindmap_json = json_blocks[0]

  return mindmap_json


if __name__ == "__main__":
  topic = """
  招聘基础知识
  """

  mindmap_json = mindmap_from_topic(topic)
  print(mindmap_json)
