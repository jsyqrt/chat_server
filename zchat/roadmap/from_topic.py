import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
from zchat.roadmap.common_prompts import MINDMAP_JSON_SCHEMA, MINDMAP_GENERATION_GUIDELINES

system_prompt_template = """
您是一位专业的学习路径设计专家，擅长创建结构化、全面的学习计划。您的任务是为用户提供一个详细的学习路径，帮助他们掌握所需的知识和技能。

请分析用户提供的主题，并考虑以下因素：
1. 主题的广度和深度
2. 用户当前的知识水平（如果提供）
3. 用户的学习目标（如果提供）
4. 用户的背景和经验（如果提供）
5. 该领域的最新发展和趋势

您需要创建一个全面的学习路径，包括：

1. 核心知识领域：
   - 基础概念和原理
   - 进阶理论和方法论
   - 专业工具和技术
   - 最佳实践和标准

2. 如果主题是职业或者职位或者公司组织机构中的角色，还需包括以下内容，否则不需要：
   - 必备软技能（沟通、团队协作等）
   - 行业认证和资质
   - 职业发展阶段和晋升路径
   - 不同级别的职责和要求
   - 实践项目和经验积累方法

3. 学习资源和方法：
   - 推荐的学习顺序
   - 阶段性学习目标
   - 实践应用场景

请确保您的学习路径是结构化的、渐进式的，并且适合用户的当前水平、背景和目标。
"""

user_prompt = """
请为我创建一个关于以下主题的详细学习路径，以思维导图JSON格式输出：

思维导图的JSON Schema:
${MINDMAP_JSON_SCHEMA}

${MINDMAP_GENERATION_GUIDELINES}

特别注意事项：
1. 确保思维导图总节点数不少于100个，全面覆盖相关知识点
2. 根据我提供的当前水平，调整内容深度（避免过于基础或过于高级）
3. 根据我的学习目标，突出相关重点内容
4. 考虑我的背景和经验，提供更有针对性的学习建议
5. 如果主题是职业相关的，包含职业发展路径、不同级别要求和软技能
6. 为每个主要知识领域提供学习顺序建议

如果我提供的主题涉及政治敏感、暴力、色情、赌博、毒品、枪支等敏感内容，请直接返回：
```json
null
```
"""

topic_prompt_template = """
## 学习主题
{topic}
"""

skill_level_prompt_template = """
## 当前水平
{skill_level}
"""

learning_goal_prompt_template = """
## 学习目标
{learning_goal}
"""

user_background_prompt_template = """
## 用户背景
{user_background}
"""

other_prompts_template = """
## 其他用户输入的提示，在生成思维导图时需要考虑
{other_prompts}
"""

def get_llm_response(topic, skill_level, learning_goal, user_background, other_prompts):
  messages=[
    {"role": "system", "content": system_prompt_template},
    {"role": "user", "content":
        topic_prompt_template.format(topic=topic) + \
        (skill_level_prompt_template.format(skill_level=skill_level) if skill_level else '') + \
        (learning_goal_prompt_template.format(learning_goal=learning_goal) if learning_goal else '') + \
        (user_background_prompt_template.format(user_background=user_background) if user_background else '') + \
        (other_prompts_template.format(other_prompts=other_prompts) if other_prompts else '') + \
        user_prompt.replace("${MINDMAP_JSON_SCHEMA}", MINDMAP_JSON_SCHEMA)
                .replace("${MINDMAP_GENERATION_GUIDELINES}", MINDMAP_GENERATION_GUIDELINES) },
  ]
  print(messages)
  response = get_response_from_llm(messages, "qwen-qwq-32b", 8192, platform='siliconflow')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def mindmap_from_topic(topic, skill_level, learning_goal, user_background, other_prompts):
  response = get_llm_response(topic, skill_level, learning_goal, user_background, other_prompts)
  json_blocks = parse_llm_response(response)
  print(json_blocks)
  if len(json_blocks) == 0:
    return None
  mindmap_json = json_blocks[0]

  return mindmap_json


if __name__ == "__main__":
  topic = """
  招聘基础知识
  """

  learning_goal = """
  了解招聘流程和招聘渠道
  """

  skill_level = """
  初级
  """

  user_background = """
  人力资源专业毕业，有1年HR助理经验，但没有直接负责过招聘工作
  """

  other_prompts = """
  希望能够在3个月内掌握招聘技能，并能独立负责公司的招聘工作
  """

  mindmap_json = mindmap_from_topic(topic, skill_level, learning_goal, user_background, other_prompts)
  print(mindmap_json)
