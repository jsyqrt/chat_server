import re
import openai
import os

system_prompt_template = """
请分析提供的职位描述（JD），提取所有关键信息，形成一个JSON格式的结果。关键信息应包括职位标题、地点、薪资范围、学历要求、工作年限要求、部门、主要职责和所需技能等相关字段，确保内容全面且结构清晰。
接下来，针对一个职场经验{{work_experience}}的用户，规划学习路径（包括硬技能和软技能），以达到该JD要求的水平。学习路径应使用有向图的方式表示，包含节点（需要学习的概念、技能或需要练习/实践的事项，结点数量7到10个）和边（连接相关节点，实线表示直接相关，虚线表示关联性，建议了解）。学习路径的JSON输出中，需为每个节点添加‘learning_suggestions’字段，包含具体的学习资源、方法或实践建议。
"""

user_prompt= """
请提供以下两个JSON格式的输出：
1. 职位描述的关键信息JSON，需符合以下JSON Schema：
```json
{
  "type": "object",
  "properties": {
    "job_title": { "type": "string", "description": "职位标题" },
    "location": { "type": "string", "description": "工作地点" },
    "salary_range": { "type": "string", "description": "薪资范围" },
    "education_requirement": { "type": "string", "description": "学历要求" },
    "work_experience_requirement": { "type": "string", "description": "工作年限要求" },
    "department": { "type": "string", "description": "所属部门" },
    "key_responsibilities": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "主要职责列表"
    },
    "required_skills": {
      "type": "array",
      "items": { "type": "object", "properties": { "skill": { "type": "string" }, "experience": { "type": "string" }, "description": { "type": "string" } } },
      "description": "所需技能列表"
    },
    "preferred_qualifications": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "优先条件或加分项"
    },
    "notes": { "type": "string", "description": "其他备注或加分项" }
  },
  "required": ["job_title", "key_responsibilities", "required_skills"],
  "additionalProperties": false
}
```
2. 学习路径的JSON，使用有向图表示，需符合以下JSON Schema：
```json
{
  "type": "object",
  "properties": {
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string", "description": "唯一标识符" },
          "label": { "type": "string", "description": "节点名称或标签" },
          "type": { "type": "string", "enum": ["hard_skill", "soft_skill", "practice"], "description": "节点类型" },
          "description": { "type": "string", "description": "节点详细描述" },
          "learning_suggestions": {
            "type": "array",
            "items": { "type": "string" },
            "description": "学习建议或资源"
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
确保输出严格遵循上述JSON Schema，确保数据完整性和一致性。职位描述和学习路径应针对提供的JD内容进行定制化分析和规划，使其通用且易于扩展到其他类似场景。

"""

jd_prompt_template = """
JD信息：
```text
{jd}
```
"""

def get_llm_response(jd, work_experience):
  client = openai.OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    # base_url="http://127.0.0.1:8080/v1",
  )
  response = client.chat.completions.create(
    model="qwen-2.5-32b",
    # model="mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit",
    messages=[
      {"role": "system", "content": system_prompt_template.format(work_experience=work_experience)},
      {"role": "user", "content": user_prompt + jd_prompt_template.format(jd=jd)},
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

def roadmap_from_jd(jd, work_experience):
  response = get_llm_response(jd, work_experience)
  json_blocks = parse_llm_response(response)
  jd_info_json = json_blocks[0]
  roadmap_json = json_blocks[1]

  return jd_info_json, roadmap_json


if __name__ == "__main__":
  jd = """
  25
-2025
小红书正在招聘
资深招聘专家
上海/25-40K/5-10年/本科
职位详情
1、根据业务发展的需求和编制，分解年度招聘
策略，运营各类招聘项目；
2、开拓和利用各种招聘渠道，满足公司的
人才需求；
3、建立和优化招聘流程，协调招聘团队高效
合作；
4、收集市场人才信息，进行相关行业/
人才 mapping；
5、负责招聘渠道的数据统计和分析，通过数据
确定招聘流程问题并提出解决方案。
任职要求：
1、本科及以上学历，4年以上招聘相关经验，有
招聘运营，项目管理，高招等项目经验优先；
2、优秀的项目执行能力和推进能力，具备0-1，
1-10-N等不同生命周期组织的招聘项目经验优
先；
3、具备良好的逻辑分析能力、数据分析能力、
解决问题能力、以及沟通能力；
BOSS ZHIPIN
扫码查看职位详情
找工作，上BOSS直聘直接谈
BOSS
直聘
◎
  """

  work_experience = """
  1-3年的职场新人
  """

  llm_response = get_llm_response(jd, work_experience)
  print(llm_response)
  jd_info_json = parse_llm_response(llm_response)[0]
  roadmap_json = parse_llm_response(llm_response)[1]

  print(jd_info_json)
  print(roadmap_json)
