from flask import current_app, g
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
import json
from flask_babel import gettext as _

def jd_schema(lang='zh_CN'):
    """Return the JSON schema for job description in the specified language."""
    if lang in ['en']:
        json_schema = """
{
  "type": "object",
  "properties": {
    "job_title": { "type": "string", "description": "Job title" },
    "company": { "type": "string", "description": "Company name" },
    "location": { "type": "string", "description": "Work location" },
    "salary_range": { "type": "string", "description": "Salary range" },
    "education_requirement": { "type": "string", "description": "Education requirements" },
    "work_experience_requirement": { "type": "string", "description": "Work experience requirements" },
    "department": { "type": "string", "description": "Department" },
    "job_description": { "type": "string", "description": "Job description" },
    "key_responsibilities": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "List of key responsibilities"
    },
    "required_skills": {
      "type": "array",
      "items": { "type": "object", "properties": { "skill": { "type": "string" }, "importance": { "type": "string", "enum": ["Essential", "Important", "Bonus"] }, "description": { "type": "string" } } },
      "description": "List of required skills, including skill name, importance, and description"
    },
    "preferred_qualifications": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "Preferred qualifications or bonus points"
    },
    "keywords": { "type": "array", "items": { "type": "string" }, "description": "List of keywords for skills required by the position or needed for job responsibilities" },
    "industry_context": { "type": "string", "description": "Industry background and company information" },
    "career_path": { "type": "string", "description": "Possible career path for this position" }
  },
  "required": ["job_title", "key_responsibilities", "required_skills"]
}
"""
    else:  # Default to Chinese
        json_schema = """
{
  "type": "object",
  "properties": {
    "job_title": { "type": "string", "description": "职位标题" },
    "company": { "type": "string", "description": "公司名称" },
    "location": { "type": "string", "description": "工作地点" },
    "salary_range": { "type": "string", "description": "薪资范围" },
    "education_requirement": { "type": "string", "description": "学历要求" },
    "work_experience_requirement": { "type": "string", "description": "工作年限要求" },
    "department": { "type": "string", "description": "所属部门" },
    "job_description": { "type": "string", "description": "职位描述" },
    "key_responsibilities": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "主要职责列表"
    },
    "required_skills": {
      "type": "array",
      "items": { "type": "object", "properties": { "skill": { "type": "string" }, "importance": { "type": "string", "enum": ["必备", "重要", "加分"] }, "description": { "type": "string" } } },
      "description": "所需技能列表，包括技能名称、重要性和描述"
    },
    "preferred_qualifications": {
      "type": "array",
      "items": { "type": "object", "properties": { "description": { "type": "string" } } },
      "description": "优先条件或加分项"
    },
    "keywords": { "type": "array", "items": { "type": "string" }, "description": "职位要求的技能，或工作职责所需的技能的关键词列表" },
    "industry_context": { "type": "string", "description": "行业背景和公司情况" },
    "career_path": { "type": "string", "description": "该职位可能的职业发展路径" }
  },
  "required": ["job_title", "key_responsibilities", "required_skills"]
}
"""
    return "```json\n" + json_schema + "\n```"

def parse_jd_prompt(jd_text, lang='zh_CN'):
    """Generate system and user prompts based on the language."""
    if lang in ['en']:
        system_prompt = """
You are an experienced job position analyst, skilled at analyzing job descriptions and extracting relevant information.

Job analysis:
- Carefully analyze the provided job description (JD)
- Extract all key information, including job title, location, salary, educational requirements, work experience, department, responsibilities, and skill requirements
- Identify explicit and implicit requirements
- Distinguish between essential skills and bonus skills
- Analyze possible career development paths for the position
- Extract a list of keywords for skills required by the position or needed for job responsibilities

Please respond in English.
"""
        user_prompt = f"""
Job Description:
{jd_text}

Please analyze the job description and extract relevant information, returning an object that conforms to the following JSON format:
""" + jd_schema(lang) + """

Note:
1. Your response must be a JSON-formatted object
2. If information is missing, use null or empty arrays
3. Don't miss any information
"""
    else:  # Default to Chinese
        system_prompt = """
你是一位经验丰富的职位分析专家，擅长分析职位描述并提取相关信息。

职位分析：
- 仔细分析提供的职位描述(JD)
- 提取所有关键信息，包括职位标题、地点、薪资、学历要求、工作年限、部门、职责和技能要求
- 识别明确要求和隐含要求
- 区分必备技能和加分技能
- 分析职位可能的职业发展路径
- 提取职位要求的技能，或者工作职责所需的技能的关键词列表

请用中文回答。
"""
        user_prompt = f"""
职位描述：
{jd_text}

请分析职位描述并提取相关信息，返回一个符合以下JSON格式的对象：
""" + jd_schema(lang) + """

注意：
1. 你的返回必须是一个符合JSON格式的对象
2. 如果信息缺失，请使用null或空数组
3. 不要遗漏任何信息
"""
    return system_prompt, user_prompt

def parse_jd(jd_text):
    try:
        # Get current language from Flask g object, default to zh_CN if not set
        lang = getattr(g, 'lang', 'zh_CN')
        current_app.logger.debug(f"Using language: {lang} for JD parsing")

        system_prompt, user_prompt = parse_jd_prompt(jd_text, lang)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = get_response_from_llm(messages, model="qwen-2.5-32b", max_tokens=4096, platform="siliconflow")
        blocks = get_json_blocks_from_llm_response(response)
        if len(blocks) < 1:
            raise ValueError("No JSON block found in the response")
        current_app.logger.debug(f"parse_jd_response: {blocks}")
        return json.loads(blocks[0])
    except Exception as e:
        print(f"Error parsing JD: {e}")
        return None

if __name__ == "__main__":
    from zchat.apis.ocr import ocr_file
    jd_text = ocr_file("/Users/liuqian/mycode/github/sf/be/chat_server/resumes/jd.png")
    print(jd_text)
    print(json.dumps(parse_jd(jd_text), indent=2, ensure_ascii=False))
