import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
from zchat.roadmap.common_prompts import MINDMAP_JSON_SCHEMA, MINDMAP_GENERATION_GUIDELINES

system_prompt = """
您是一位专业的职业发展顾问和学习路径规划专家，擅长分析职位描述并创建个性化学习计划。

请完成以下两项任务：

1. 职位描述分析：
   - 仔细分析提供的职位描述(JD)
   - 提取所有关键信息，包括职位标题、地点、薪资、学历要求、工作年限、部门、职责和技能要求
   - 识别明确要求和隐含要求
   - 区分必备技能和加分技能

2. 学习路径规划：
   - 基于JD分析结果，创建一个全面的学习路径
   - 考虑用户当前的职业背景和技能水平(如果提供)
   - 设计一个结构化的、渐进式的学习计划
   - 包含技术技能、软技能、行业知识和职业发展策略
   - 以思维导图形式呈现，确保逻辑连贯且覆盖全面

您的分析应当专业、全面且实用，帮助求职者清晰了解职位要求并有效准备。
"""

user_prompt = """
针对JD的特殊要求：
- 分析JD中明确和隐含的技能要求
- 将学习路径分为短期目标(应对面试)和长期目标(职业发展)
- 包含该职位所需的行业知识和专业术语
- 如果用户提供了简历信息，根据用户当前技能水平定制学习路径
- 为每个主要技能提供学习资源建议和实践项目

${MINDMAP_GENERATION_GUIDELINES}

请提供用JSON格式表示的思维导图，思维导图的JSON Schema:
${MINDMAP_JSON_SCHEMA}

确保JSON格式正确无误，可以被直接解析。不要添加额外的解释或注释。
"""

jd_prompt_template = """
## 职位描述
```
{jd}
```

请仔细分析上述职位描述，提取所有明确和隐含的要求，包括技术技能、软技能、行业知识和经验要求。
"""

resume_prompt_template = """
## 用户简历信息
```
{resume}
```

请根据用户的职场经验和已掌握的技能，调整学习路径，重点关注用户需要提升的领域，避免已掌握的基础内容。
"""


def get_llm_response(jd, resume):
  messages=[
      {"role": "system", "content": system_prompt},
      {"role": "user", "content":  jd_prompt_template.format(jd=jd) + \
                                    (resume_prompt_template.format(resume=resume) if resume else '') + \
                                    user_prompt.replace("${MINDMAP_JSON_SCHEMA}", MINDMAP_JSON_SCHEMA)
                                            .replace("${MINDMAP_GENERATION_GUIDELINES}", MINDMAP_GENERATION_GUIDELINES) },
    ]
  print(messages)
  response = get_response_from_llm(messages, "qwen-qwq-32b", 8192, platform='siliconflow')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def mindmap_from_jd_and_resume(jd, resume):
  response = get_llm_response(jd, resume)
  json_blocks = parse_llm_response(response)
  if len(json_blocks) < 1:
    return None

  mindmap_json = json_blocks[0]

  return mindmap_json


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
  mindmap_json = parse_llm_response(llm_response)[1]

  print(jd_info_json)
  print(mindmap_json)
