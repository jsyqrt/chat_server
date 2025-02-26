import re
import openai
import os

system_prompt_template = """
请分析提供的topic，生成一个学习路径。
学习路径应使用有向图的方式表示，包含节点（需要学习的概念、技能或需要练习/实践的事项或不同学习阶段，结点数量至少10个）和边（连接相关节点，实线表示直接相关，虚线表示关联性，建议了解）。学习路径的JSON输出中，需为每个节点添加‘learning_suggestions’字段，包含具体的学习资源、方法或实践建议。
学习路径应该详细分析topic，拆分出多个子topic，以及多个学习阶段。每个学习阶段顺序连接若干个topic，每个topic连接若干个子topic。不同的学习阶段顺序相连。
"""

user_prompt= """
请提供以下JSON格式的输出，使用有向图表示，需符合以下JSON Schema：
```json
{
  "type": "object",
  "properties": {
    "topic": { "type": "string", "description": "detailed description of the topic" },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string", "description": "唯一标识符" },
          "label": { "type": "string", "description": "节点名称或标签" },
          "type": { "type": "string", "enum": ["hard_skill", "soft_skill", "practice", "stage"], "description": "节点类型" },
          "description": { "type": "string", "description": "节点详细描述" },
          "learning_suggestions": {
            "type": "array",
            "items": { "type": "string" },
            "description": "学习建议或资源，或学习阶段描述"
          }
        },
        "required": ["id", "label", "type", "description", "learning_suggestions"]
      },
      "description": "学习路径中的节点"
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "from": { "type": "string", "description": "起始节点ID" },
          "to": { "type": "string", "description": "目标节点ID" },
          "type": { "type": "string", "enum": ["solid", "dashed"], "description": "边类型（实线或虚线）" },
          "description": { "type": "string", "description": "边关系的描述" }
        },
        "required": ["from", "to", "type", "description"]
      },
      "description": "节点之间的关系"
    }
  },
  "required": ["nodes", "edges"],
  "additionalProperties": false
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

def roadmap_from_topic(topic):
  response = get_llm_response(topic)
  json_blocks = parse_llm_response(response)
  roadmap_json = json_blocks[0]

  return roadmap_json


if __name__ == "__main__":
  topic = """
  招聘基础知识
  """

  roadmap_json = roadmap_from_topic(topic)
  print(roadmap_json)
