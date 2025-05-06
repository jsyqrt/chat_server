import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
from zchat.roadmap.common_prompts import MINDMAP_JSON_SCHEMA, MINDMAP_GENERATION_GUIDELINES_ZH, MINDMAP_GENERATION_GUIDELINES_EN

# Chinese system prompt
system_prompt_template_zh = """
您是一位专业的学习路径设计专家，擅长创建结构化、全面的学习计划。您的任务是为用户提供一个详细的学习路径，帮助他们掌握所需的知识和技能。

主题可能是行业、职业、技能、技能组、概念等不同类型，请根据主题的类型，选择合适的知识范围和深度。

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

2. 如果主题是行业类型，还需包括以下内容：
   - 行业现状和趋势
   - 行业标准和规范
   - 行业最佳实践
   - 行业未来发展方向，包括AI时代下的行业发展趋势

3. 如果主题是职业类型，还需包括以下内容：
   - 必备软技能（沟通、团队协作等）
   - 行业认证和资质
   - 职业发展阶段和晋升路径
   - 不同级别的职责和要求
   - 实践项目和经验积累方法
   - 其他相关的职业信息，包括行业，技能，发展趋势等
   - AI时代下的职业发展趋势，包括AI对职业的影响，AI时代下的职业发展路径等

4. 如果主题是技能或者技能组类型，还需包括以下内容：
   - 技能的定义和分类
   - 技能的实践方法
   - 技能的评估标准
   - 技能的实践项目
   - 技能的进阶路径
   - 其他相关的技能
   - AI时代下的技能发展趋势，包括使用AI工具和平台等

5. 如果主题是概念类型，区分主题是关于行业，职业，技能，技能组，还是其他概念，并根据对应的类型，选择合适的知识范围和深度。

6. 学习资源和方法：
   - 推荐的学习顺序
   - 阶段性学习目标
   - 实践应用场景

请确保您的学习路径是结构化的、渐进式的，并且适合用户的当前水平、背景和目标。
"""

# English system prompt
system_prompt_template_en = """
You are a professional learning path design expert, skilled in creating structured, comprehensive learning plans. Your task is to provide users with a detailed learning path to help them master the necessary knowledge and skills.

The topic could be related to industry, profession, skills, skill groups, concepts, or other types. Please select an appropriate knowledge scope and depth based on the type of topic.

Please analyze the user-provided topic and consider the following factors:
1. The breadth and depth of the topic
2. The user's current knowledge level (if provided)
3. The user's learning goals (if provided)
4. The user's background and experience (if provided)
5. The latest developments and trends in the field

You need to create a comprehensive learning path, including:

1. Core knowledge domains:
   - Basic concepts and principles
   - Advanced theories and methodologies
   - Professional tools and technologies
   - Best practices and standards

2. If the topic is industry-related, also include:
   - Industry status and trends
   - Industry standards and norms
   - Industry best practices
   - Future directions of the industry, including trends in the AI era

3. If the topic is profession-related, also include:
   - Essential soft skills (communication, teamwork, etc.)
   - Industry certifications and qualifications
   - Career development stages and promotion paths
   - Responsibilities and requirements at different levels
   - Practical projects and methods for experience accumulation
   - Other relevant career information, including industry, skills, development trends, etc.
   - Career development trends in the AI era, including AI's impact on the profession and career paths in the AI era

4. If the topic is skill or skill group-related, also include:
   - Skill definitions and classifications
   - Skill practice methods
   - Skill assessment standards
   - Skill practice projects
   - Skill advancement paths
   - Other related skills
   - Skill development trends in the AI era, including using AI tools and platforms

5. If the topic is concept-related, distinguish whether the topic is about industry, profession, skills, skill groups, or other concepts, and select an appropriate knowledge scope and depth accordingly.

6. Learning resources and methods:
   - Recommended learning sequence
   - Stage-by-stage learning objectives
   - Practical application scenarios

Please ensure your learning path is structured, progressive, and suitable for the user's current level, background, and goals.
"""

# Chinese user prompt
user_prompt_zh = """
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

# English user prompt
user_prompt_en = """
Please create a detailed learning path for the following topic, output in mind map JSON format:

Mind Map JSON Schema:
${MINDMAP_JSON_SCHEMA}

${MINDMAP_GENERATION_GUIDELINES}

Special considerations:
1. Ensure the mind map has at least 100 nodes total, comprehensively covering related knowledge points
2. Adjust content depth based on my provided current level (avoid being too basic or too advanced)
3. Highlight relevant key content based on my learning goals
4. Consider my background and experience to provide more targeted learning suggestions
5. If the topic is career-related, include career development path, requirements at different levels, and soft skills
6. Provide learning sequence suggestions for each major knowledge domain

If the topic I provide involves politically sensitive content, violence, pornography, gambling, drugs, firearms, or other sensitive content, please return directly:
```json
null
```
"""

topic_prompt_template_zh = """
## 学习主题
{topic}
"""

topic_prompt_template_en = """
## Learning Topic
{topic}
"""

kind_prompt_template_zh = """
## 学习主题类型
{kind}
"""

kind_prompt_template_en = """
## Learning Topic Type
{kind}
"""

skill_level_prompt_template_zh = """
## 当前水平
{skill_level}
"""

skill_level_prompt_template_en = """
## Current Level
{skill_level}
"""

learning_goal_prompt_template_zh = """
## 学习目标
{learning_goal}
"""

learning_goal_prompt_template_en = """
## Learning Goal
{learning_goal}
"""

user_background_prompt_template_zh = """
## 用户背景
{user_background}
"""

user_background_prompt_template_en = """
## User Background
{user_background}
"""

other_prompts_template_zh = """
## 用户输入的其他提示，在生成思维导图时需要考虑
{other_prompts}
"""

other_prompts_template_en = """
## Other prompts from the user to consider when generating the mind map
{other_prompts}
"""

def get_prompts_by_language(lang):
    """Get the appropriate prompts based on the user's language"""
    if lang == 'en':
        return {
            'system_prompt': system_prompt_template_en,
            'user_prompt': user_prompt_en,
            'topic_prompt': topic_prompt_template_en,
            'kind_prompt': kind_prompt_template_en,
            'skill_level_prompt': skill_level_prompt_template_en,
            'learning_goal_prompt': learning_goal_prompt_template_en,
            'user_background_prompt': user_background_prompt_template_en,
            'other_prompts_template': other_prompts_template_en,
            'mindmap_guidelines': MINDMAP_GENERATION_GUIDELINES_EN
        }
    else:  # default to Chinese (zh_CN or zh_TW)
        return {
            'system_prompt': system_prompt_template_zh,
            'user_prompt': user_prompt_zh,
            'topic_prompt': topic_prompt_template_zh,
            'kind_prompt': kind_prompt_template_zh,
            'skill_level_prompt': skill_level_prompt_template_zh,
            'learning_goal_prompt': learning_goal_prompt_template_zh,
            'user_background_prompt': user_background_prompt_template_zh,
            'other_prompts_template': other_prompts_template_zh,
            'mindmap_guidelines': MINDMAP_GENERATION_GUIDELINES_ZH
        }

def get_llm_response(topic, kind, skill_level, learning_goal, user_background, other_prompts, lang='zh_CN'):
  prompts = get_prompts_by_language(lang)
  messages=[
    {"role": "system", "content": prompts['system_prompt']},
    {"role": "user", "content":
        prompts['topic_prompt'].format(topic=topic) + \
        (prompts['kind_prompt'].format(kind=kind) if kind else '') + \
        (prompts['skill_level_prompt'].format(skill_level=skill_level) if skill_level else '') + \
        (prompts['learning_goal_prompt'].format(learning_goal=learning_goal) if learning_goal else '') + \
        (prompts['user_background_prompt'].format(user_background=user_background) if user_background else '') + \
        (prompts['other_prompts_template'].format(other_prompts=other_prompts) if other_prompts else '') + \
        prompts['user_prompt'].replace("${MINDMAP_JSON_SCHEMA}", MINDMAP_JSON_SCHEMA)
                .replace("${MINDMAP_GENERATION_GUIDELINES}", prompts['mindmap_guidelines']) },
  ]
  print(messages)
  response = get_response_from_llm(messages, "qwen-qwq-32b", 8192, platform='siliconflow')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def mindmap_from_topic(topic, kind, skill_level, learning_goal, user_background, other_prompts, lang='zh_CN'):
  response = get_llm_response(topic, kind, skill_level, learning_goal, user_background, other_prompts, lang)
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

  kind = """
  job
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

  mindmap_json = mindmap_from_topic(topic, kind, skill_level, learning_goal, user_background, other_prompts)
  print(mindmap_json)
