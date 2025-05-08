from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
import json
from flask import g

def resume_schema():
    # Check the current language from Flask g object
    lang = getattr(g, 'lang', 'zh_CN')

    if lang.startswith('en'):
        # English version of the schema
        json_schema = """
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Candidate's full name"
    },
    "contact": {
      "type": "object",
      "properties": {
        "email": {
          "type": "string",
          "description": "Email address"
        },
        "phone": {
          "type": "string",
          "description": "Phone number"
        },
        "linkedin": {
          "type": "string",
          "description": "LinkedIn profile URL"
        },
        "github": {
          "type": "string",
          "description": "GitHub profile URL"
        },
        "website": {
          "type": "string",
          "description": "Personal website URL"
        },
        "address": {
          "type": "string",
          "description": "Physical address (if any)"
        }
      }
    },
    "personal_info": {
      "type": "object",
      "properties": {
        "nationality": {
          "type": "string",
          "description": "Nationality (if mentioned)"
        },
        "languages": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "language": {
                "type": "string",
                "description": "Language name"
              },
              "proficiency": {
                "type": "string",
                "description": "Proficiency level"
              }
            }
          }
        },
        "other_details": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "description": "Personal information name"
              },
              "value": {
                "type": "string",
                "description": "Personal information value"
              }
            }
          }
        }
      }
    },
    "education": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "degree": {
            "type": "string",
            "description": "Degree name or study program"
          },
          "field_of_study": {
            "type": "string",
            "description": "Major or field of study"
          },
          "institution": {
            "type": "string",
            "description": "Institution name"
          },
          "location": {
            "type": "string",
            "description": "Institution location"
          },
          "start_date": {
            "type": "string",
            "description": "Education start date"
          },
          "end_date": {
            "type": "string",
            "description": "Education end date or expected graduation date"
          },
          "gpa": {
            "type": "string",
            "description": "GPA or academic achievements"
          },
          "details": {
            "type": "string",
            "description": "Other details about the education"
          }
        }
      }
    },
    "self_evaluation": {
      "type": "string",
      "description": "Self-evaluation"
    },
    "interests": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Personal or professional interests"
    },
    "good_at": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Strengths, things the person is good at"
    },
    "skills": {
      "type": "object",
      "properties": {
        "technical": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Technical skills (programming languages, tools, platforms and proficiency level, e.g., familiar with XX, knowledge of YY, expert in ZZ)"
        },
        "soft": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Soft skills (communication, leadership, etc., e.g., strong communication skills, strong teamwork abilities, strong stress resistance)"
        },
        "languages": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Language skills (e.g., fluent in English, proficient in Japanese)"
        },
        "other": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Other skills that don't fit the above categories (e.g., good at communication, writing, design)"
        }
      }
    },
    "certifications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Certificate name"
          },
          "issuer": {
            "type": "string",
            "description": "Issuing institution"
          },
          "date": {
            "type": "string",
            "description": "Date obtained"
          },
          "expiration": {
            "type": "string",
            "description": "Expiration date (if applicable)"
          },
          "id": {
            "type": "string",
            "description": "Certificate ID (if any)"
          },
          "url": {
            "type": "string",
            "description": "URL to verify certificate (if any)"
          }
        }
      }
    },
    "experience": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "Job title"
          },
          "organization": {
            "type": "string",
            "description": "Organization or company name"
          },
          "location": {
            "type": "string",
            "description": "Work location"
          },
          "start_date": {
            "type": "string",
            "description": "Employment start date"
          },
          "end_date": {
            "type": "string",
            "description": "Employment end date or 'Present' (if current job)"
          },
          "description": {
            "type": "string",
            "description": "Overall job description"
          },
          "responsibilities": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Main responsibilities of the role"
          },
          "achievements": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Specific achievements, metrics, or results"
          },
          "technologies": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Technologies, tools, or methods used"
          }
        }
      }
    },
    "projects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Project name"
          },
          "role": {
            "type": "string",
            "description": "Role in the project"
          },
          "start_date": {
            "type": "string",
            "description": "Project start date"
          },
          "end_date": {
            "type": "string",
            "description": "Project end date or 'Present' (if ongoing)"
          },
          "description": {
            "type": "string",
            "description": "Project description"
          },
          "technologies": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Technologies, tools, or methods used"
          },
          "achievements": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Specific achievements or outcomes"
          },
          "url": {
            "type": "string",
            "description": "Project URL (if any)"
          }
        }
      }
    },
    "publications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "Publication title"
          },
          "authors": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "List of authors"
          },
          "publisher": {
            "type": "string",
            "description": "Publisher or journal name"
          },
          "date": {
            "type": "string",
            "description": "Publication date"
          },
          "url": {
            "type": "string",
            "description": "Publication URL (if any)"
          },
          "description": {
            "type": "string",
            "description": "Publication description or abstract"
          }
        }
      }
    },
    "awards": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Award name"
          },
          "issuer": {
            "type": "string",
            "description": "Issuing institution"
          },
          "date": {
            "type": "string",
            "description": "Award date"
          },
          "description": {
            "type": "string",
            "description": "Award description"
          }
        }
      }
    },
    "volunteer_experience": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "role": {
            "type": "string",
            "description": "Volunteer role"
          },
          "organization": {
            "type": "string",
            "description": "Organization name"
          },
          "start_date": {
            "type": "string",
            "description": "Start date"
          },
          "end_date": {
            "type": "string",
            "description": "End date or 'Present' (if current)"
          },
          "description": {
            "type": "string",
            "description": "Volunteer work description"
          }
        }
      }
    }
  },
  "required": ["name", "contact", "education", "self_evaluation", "interests", "good_at", "skills", "experience", "projects", "publications", "awards", "volunteer_experience"]
}
"""
    else:
        # Chinese version of the schema (default)
        json_schema = """
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "候选人全名"
    },
    "contact": {
      "type": "object",
      "properties": {
        "email": {
          "type": "string",
          "description": "电子邮件地址"
        },
        "phone": {
          "type": "string",
          "description": "电话号码"
        },
        "linkedin": {
          "type": "string",
          "description": "LinkedIn个人资料URL"
        },
        "github": {
          "type": "string",
          "description": "GitHub个人资料URL"
        },
        "website": {
          "type": "string",
          "description": "个人网站URL"
        },
        "address": {
          "type": "string",
          "description": "实际地址（如有）"
        }
      }
    },
    "personal_info": {
      "type": "object",
      "properties": {
        "nationality": {
          "type": "string",
          "description": "国籍（如有提及）"
        },
        "languages": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "language": {
                "type": "string",
                "description": "语言名称"
              },
              "proficiency": {
                "type": "string",
                "description": "熟练程度"
              }
            }
          }
        },
        "other_details": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "description": "个人信息名称"
              },
              "value": {
                "type": "string",
                "description": "个人信息值"
              }
            }
          }
        }
      }
    },
    "education": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "degree": {
            "type": "string",
            "description": "学位名称或学习项目"
          },
          "field_of_study": {
            "type": "string",
            "description": "专业或研究领域"
          },
          "institution": {
            "type": "string",
            "description": "院校名称"
          },
          "location": {
            "type": "string",
            "description": "院校所在地"
          },
          "start_date": {
            "type": "string",
            "description": "教育开始日期"
          },
          "end_date": {
            "type": "string",
            "description": "教育结束日期或预期毕业日期"
          },
          "gpa": {
            "type": "string",
            "description": "GPA或学术成就"
          },
          "details": {
            "type": "string",
            "description": "关于教育的其他详细信息"
          }
        }
      }
    },
    "self_evaluation": {
      "type": "string",
      "description": "自我评价"
    },
    "interests": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "个人或职业兴趣"
    },
    "good_at": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "特长，擅长的事情"
    },
    "skills": {
      "type": "object",
      "properties": {
        "technical": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "技术技能（编程语言、工具、平台及其掌握程度，比如熟悉XX，了解YY，精通ZZ）"
        },
        "soft": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "软技能（沟通、领导力等，比如沟通能力强，有很强的团队协作能力，有很强的抗压能力）"
        },
        "languages": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "语言技能（比如英语流利，日语熟练）"
        },
        "other": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "不适合上述类别的其他技能（比如擅长沟通，擅长写作，擅长设计）"
        }
      }
    },
    "certifications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "证书名称"
          },
          "issuer": {
            "type": "string",
            "description": "颁发机构"
          },
          "date": {
            "type": "string",
            "description": "获得日期"
          },
          "expiration": {
            "type": "string",
            "description": "到期日期（如适用）"
          },
          "id": {
            "type": "string",
            "description": "证书ID（如有）"
          },
          "url": {
            "type": "string",
            "description": "验证证书的URL（如有）"
          }
        }
      }
    },
    "experience": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "职位名称"
          },
          "organization": {
            "type": "string",
            "description": "组织或公司名称"
          },
          "location": {
            "type": "string",
            "description": "工作地点"
          },
          "start_date": {
            "type": "string",
            "description": "就业开始日期"
          },
          "end_date": {
            "type": "string",
            "description": "就业结束日期或'至今'（如果是当前工作）"
          },
          "description": {
            "type": "string",
            "description": "整体工作描述"
          },
          "responsibilities": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "该角色的主要职责"
          },
          "achievements": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "具体成就、指标或结果"
          },
          "technologies": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "使用的技术、工具或方法"
          }
        }
      }
    },
    "projects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "项目名称"
          },
          "role": {
            "type": "string",
            "description": "在项目中的角色"
          },
          "start_date": {
            "type": "string",
            "description": "项目开始日期"
          },
          "end_date": {
            "type": "string",
            "description": "项目结束日期或'至今'（如果正在进行）"
          },
          "description": {
            "type": "string",
            "description": "项目描述"
          },
          "technologies": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "使用的技术、工具或方法"
          },
          "achievements": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "具体成就或成果"
          },
          "url": {
            "type": "string",
            "description": "项目URL（如有）"
          }
        }
      }
    },
    "publications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "出版物名称"
          },
          "authors": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "作者列表"
          },
          "publisher": {
            "type": "string",
            "description": "出版商或期刊名称"
          },
          "date": {
            "type": "string",
            "description": "出版日期"
          },
          "url": {
            "type": "string",
            "description": "出版物URL（如有）"
          },
          "description": {
            "type": "string",
            "description": "出版物简介或摘要"
          }
        }
      }
    },
    "awards": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "奖项名称"
          },
          "issuer": {
            "type": "string",
            "description": "颁发机构"
          },
          "date": {
            "type": "string",
            "description": "获奖日期"
          },
          "description": {
            "type": "string",
            "description": "奖项简介"
          }
        }
      }
    },
    "volunteer_experience": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "role": {
            "type": "string",
            "description": "志愿者角色"
          },
          "organization": {
            "type": "string",
            "description": "组织名称"
          },
          "start_date": {
            "type": "string",
            "description": "开始日期"
          },
          "end_date": {
            "type": "string",
            "description": "结束日期或'至今'（如果是当前工作）"
          },
          "description": {
            "type": "string",
            "description": "志愿者工作描述"
          }
        }
      }
    }
  },
  "required": ["name", "contact", "education", "self_evaluation", "interests", "good_at", "skills", "experience", "projects", "publications", "awards", "volunteer_experience"]
}
"""
    return "```json\n" + json_schema + "\n```"

def parse_resume_prompt(resume_text):
    # Check the current language from Flask g object
    lang = getattr(g, 'lang', 'zh_CN')

    if lang.startswith('en'):
        # English version of the prompts
        system_prompt = """
You are an experienced resume analysis expert, skilled at extracting structured information from resumes of various formats and styles. Your task is to carefully analyze the provided resume text and extract all relevant information into the specified JSON format.

As a professional resume analysis expert, you should:
1. Thoroughly understand all parts of the resume, including personal information, educational background, work experience, skills, project experience, etc.
2. Identify dates, contact information, and professional terminology in different formats
3. Infer information categories from context, even without explicit headings
4. Process multilingual resumes and extract information correctly
5. Identify skill types (technical skills, soft skills, etc.) and categorize them appropriately

Analysis guidelines:
- Read the entire resume carefully to ensure no information is missed
- Extract specific responsibilities, achievements, and technologies used for work experience and projects
- Distinguish between core skills and auxiliary skills
- Pay attention to date formats and ensure time periods are correctly parsed
- If there is ambiguous or unclear information in the resume, try to infer from context, but do not fabricate non-existent information
- For missing information, use null or empty arrays rather than filling in with guessed data
"""

        user_prompt = f"""
Here is the resume text to analyze:

{resume_text}

Please analyze the above resume and extract relevant information, returning a JSON object that conforms to the following JSON Schema:
""" + resume_schema() + """

Analysis requirements:
1. Your response must be a valid JSON object conforming to the above Schema
2. Extract all information that can be found in the resume, including but not limited to:
   - Personal information (name, contact details, etc.)
   - Educational background (schools, degrees, majors, time periods, etc.)
   - Work experience (companies, positions, time periods, responsibilities, achievements, etc.)
   - Skills (technical skills, soft skills, etc.)
   - Project experience (project names, descriptions, technologies used, etc.)
   - Certifications, awards, volunteer experience, and other information
3. For information not explicitly provided in the resume, use null or empty arrays
4. Do not add information that does not exist in the resume
5. Extract detailed information where possible, such as separating job responsibilities and achievements
6. Skills should be categorized by type (technical skills, soft skills, etc.)
7. Date information should include start and end times when possible

Please ensure your analysis is comprehensive, accurate, and returns JSON in the correct format.
"""
    else:
        # Chinese version of the prompts (default)
        system_prompt = """
你是一位经验丰富的简历分析专家，擅长从各种格式和风格的简历中提取结构化信息。你的任务是仔细分析提供的简历文本，并提取所有相关信息到指定的JSON格式中。

作为专业的简历分析专家，你应该：
1. 全面理解简历的各个部分，包括个人信息、教育背景、工作经验、技能、项目经验等
2. 能够识别不同格式的日期、联系方式和专业术语
3. 能够从上下文推断信息的类别，即使没有明确的标题
4. 能够处理多语言简历，并正确提取信息
5. 能够识别技能类型（技术技能、软技能等）并适当分类

分析指南：
- 仔细阅读整个简历，确保不遗漏任何信息
- 对于工作经验和项目，提取具体的职责、成就和使用的技术
- 区分核心技能和辅助技能
- 注意日期格式，确保正确解析时间段
- 如果简历中有模糊或不明确的信息，尝试从上下文推断，但不要编造不存在的信息
- 对于缺失的信息，使用null或空数组，不要填充猜测的数据
"""

        user_prompt = f"""
以下是需要分析的简历文本：

{resume_text}

请分析上述简历并提取相关信息，返回一个符合以下JSON Schema的JSON对象：
""" + resume_schema() + """

分析要求：
1. 你的返回必须是一个有效的JSON对象，符合上述Schema
2. 提取所有可以从简历中找到的信息，包括但不限于：
   - 个人信息（姓名、联系方式等）
   - 教育背景（学校、学位、专业、时间段等）
   - 工作经验（公司、职位、时间段、职责、成就等）
   - 技能（技术技能、软技能等）
   - 项目经验（项目名称、描述、使用技术等）
   - 证书、奖项、志愿者经历等其他信息
3. 对于简历中没有明确提供的信息，使用null或空数组
4. 不要添加简历中不存在的信息
5. 尽可能提取详细信息，例如将工作职责和成就分开列出
6. 技能应根据类型分类（技术技能、软技能等）
7. 日期信息应尽量包含开始和结束时间

请确保你的分析全面、准确，并且返回的JSON格式正确。
"""

    return system_prompt, user_prompt

def parse_resume(resume_text):
    system_prompt, user_prompt = parse_resume_prompt(resume_text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    response = get_response_from_llm(messages, model="qwen-2.5-32b", max_tokens=4096, platform="siliconflow")
    blocks = get_json_blocks_from_llm_response(response)
    if len(blocks) < 1:
        raise ValueError("No JSON block found in the response")
    return json.loads(blocks[0])

if __name__ == "__main__":
    from zchat.apis.ocr import ocr_file
    resume_text = ocr_file("/Users/liuqian/mycode/github/sf/be/chat_server/resumes/2.jpeg")
    print(resume_text)
    print(json.dumps(parse_resume(resume_text), indent=2, ensure_ascii=False))
