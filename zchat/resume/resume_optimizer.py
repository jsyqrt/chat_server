import json
import os
import sys
import tempfile
import argparse

from flask import current_app

from zchat.apis.ocr import ocr_file
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response

def optimization_schema():
    json_schema = """
{
  "type": "object",
  "properties": {
    "optimized_resume": {
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
    },
    "learning_suggestions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "skill": {
            "type": "string",
            "description": "需要学习的技能或知识领域"
          },
          "relevance": {
            "type": "string",
            "enum": ["高", "中", "低"],
            "description": "与职位描述的相关性"
          }
        },
        "required": ["skill", "relevance"]
      }
    }
  },
  "required": ["optimized_resume", "learning_suggestions"]
}
"""
    return json_schema

def optimize_resume_prompt(jd_text, resume_text):
    system_prompt = f"""
你是专业的简历优化专家，你的任务是根据给定的职位描述和一份求职者的简历，优化该简历以使其更好地匹配职位描述。

作为专业的简历优化专家，你应该：
1. 仔细分析职位描述，识别关键要求、技能和资格
2. 全面理解候选人的简历内容，包括经验、技能和成就
3. 整理完整的优化方案，以使简历更好地匹配职位要求
4. 确保所有优化都基于简历中已有的信息，不捏造或过度夸大事实
5. 保持候选人的专业形象和简历的真实性

优化指南：
- 重新措辞现有内容以突出与职位相关的经验和技能
- 使用职位描述中的关键词，但仅当它们真实反映候选人的技能和经验时
- 调整技能部分的顺序，将最相关的技能放在前面
- 除非简历中已经明确提到求职者精通某项技能，否则不要添加精通某项技能的描述，最多只能添加熟悉某项技能的描述
- 量化成就，但只使用简历中已有的数据或合理的估计
- 不要编造工作经验、教育背景或技能
- 不要过度夸大成就或责任

注意：职位描述和原始简历是来自OCR的结果，可能存在错别字，请根据上下文内容，修正可能的错别字，不要让错别字出现在结果中。
"""
    user_prompt = f"""
# 职位描述
{jd_text}

# 原始简历
{resume_text}

请分析职位描述和简历，整理完整的优化方案，然后按照你的优化方案，优化简历。

最后以JSON形式给出以下内容：
1. 优化后的完整简历，包含了所有可能的优化，需要注意：
   - 只润色和重组现有内容，不添加不存在的经验或技能
   - 使用职位描述中的关键词，但只用于真实反映候选人背景的情况
   - 保持简历的真实性和准确性
   - 突出与职位最相关的经验和技能
2. 列出用户可以通过学习快速提升的技能列表（基于简历与职位要求之间的差距）

重要提示：
- 不要捏造任何事实、经验、技能或成就
- 不要过度夸大候选人的资格或能力
- 确保所有优化都基于简历中已有的信息
- 使用和原始简历相同的语言, 比如如果原始简历是中文，那么优化后的简历也必须是中文, 如果原始简历是英文，那么优化后的简历也必须是英文

你的返回必须是一个有效的JSON对象，必须符合以下的JSON Schema：
""" + optimization_schema()
    return system_prompt, user_prompt

def comparison_schema():
    json_schema = """
{
  "type": "object",
  "properties": {
    "job_title": {
      "type": "string",
      "description": "职位描述中的职位名称"
    },
    "match_scores": {
      "type": "object",
      "properties": {
        "overall": {
          "type": "object",
          "properties": {
            "before": {
              "type": "integer",
              "description": "优化前的整体匹配百分比"
            },
            "after": {
              "type": "integer",
              "description": "优化后的整体匹配百分比"
            },
            "improvement": {
              "type": "integer",
              "description": "提升的百分点"
            }
          }
        },
        "skill_match": {
          "type": "object",
          "properties": {
            "before": {
              "type": "integer",
              "description": "优化前的技能匹配百分比"
            },
            "after": {
              "type": "integer",
              "description": "优化后的技能匹配百分比"
            },
            "improvement": {
              "type": "integer",
              "description": "提升的百分点"
            }
          }
        },
        "experience_match": {
          "type": "object",
          "properties": {
            "before": {
              "type": "integer",
              "description": "优化前的经验匹配百分比"
            },
            "after": {
              "type": "integer",
              "description": "优化后的经验匹配百分比"
            },
            "improvement": {
              "type": "integer",
              "description": "提升的百分点"
            }
          }
        },
        "education_match": {
          "type": "object",
          "properties": {
            "before": {
              "type": "integer",
              "description": "优化前的教育匹配百分比"
            },
            "after": {
              "type": "integer",
              "description": "优化后的教育匹配百分比"
            },
            "improvement": {
              "type": "integer",
              "description": "提升的百分点"
            }
          }
        }
      }
    },
    "keywords": {
      "type": "object",
      "properties": {
        "before": {
          "type": "integer",
          "description": "优化前匹配的关键词数量"
        },
        "after": {
          "type": "integer",
          "description": "优化后匹配的关键词数量"
        },
        "improvement": {
          "type": "integer",
          "description": "额外匹配的关键词数量"
        },
        "keyword_list": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "keyword": {
                "type": "string",
                "description": "职位描述中的关键词"
              },
              "before": {
                "type": "boolean",
                "description": "优化前关键词是否存在"
              },
              "after": {
                "type": "boolean",
                "description": "优化后关键词是否存在"
              }
            }
          }
        }
      }
    },
    "skill_comparisons": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "技能名称"
          },
          "before_score": {
            "type": "integer",
            "description": "优化前的得分"
          },
          "after_score": {
            "type": "integer",
            "description": "优化后的得分"
          },
          "improvement": {
            "type": "integer",
            "description": "提升量"
          },
          "relevance": {
            "type": "string",
            "enum": ["高", "中", "低"],
            "description": "该技能对职位描述的相关性"
          }
        },
        "required": ["name", "before_score", "after_score", "improvement"]
      }
    },
    "section_comparisons": {
      "type": "object",
      "properties": {
        "skills": {
          "type": "object",
          "properties": {
            "before": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "原始技能"
            },
            "after": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "优化后的技能"
            },
            "changes": {
              "type": "array",
              "items": {
                "type": "string",
                "description": "所做更改的描述"
              }
            }
          }
        },
        "experiences": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "position": {
                "type": "string",
                "description": "职位名称"
              },
              "before": {
                "type": "string",
                "description": "原始经验描述"
              },
              "after": {
                "type": "string",
                "description": "优化后的经验描述"
              },
              "changes": {
                "type": "array",
                "items": {
                  "type": "string",
                  "description": "所做更改的描述"
                }
              }
            }
          }
        },
        "educations": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "degree": {
                "type": "string",
                "description": "学位名称"
              },
              "before": {
                "type": "string",
                "description": "原始教育描述"
              },
              "after": {
                "type": "string",
                "description": "优化后的教育描述"
              },
              "changes": {
                "type": "array",
                "items": {
                  "type": "string",
                  "description": "所做更改的描述"
                }
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
              "before": {
                "type": "string",
                "description": "原始项目描述"
              },
              "after": {
                "type": "string",
                "description": "优化后的项目描述"
              },
              "changes": {
                "type": "array",
                "items": {
                  "type": "string",
                  "description": "所做更改的描述"
                }
              }
            }
          }
        }
      }
    },
    "improvement_summary": {
      "type": "array",
      "items": {
        "type": "string",
        "description": "对简历所做主要改进的总结"
      }
    }
  },
  "required": ["job_title", "match_scores", "keywords", "skill_comparisons", "section_comparisons", "improvement_summary"]
}
"""
    return json_schema

def compare_resumes_prompt(jd_text, original_resume, optimized_resume):
    system_prompt = f"""
你是专业的简历分析专家，你的任务是比较原始简历和针对目标岗位优化后的简历，分析优化效果。

作为专业的简历分析专家，你应该：
1. 仔细分析职位描述、原始简历和优化后的简历
2. 比较原始简历和优化后的简历在各方面的匹配度
3. 识别关键改进和变化
4. 提供客观、详细的分析

注意：职位描述和原始简历来自OCR的结果，可能存在错别字，请根据上下文正确处理错别字的情况。
"""
    user_prompt = f"""
# 职位描述
{jd_text}

# 原始简历
{original_resume}

# 优化后的简历
{optimized_resume}

请分析原始简历和优化后的简历，提供详细的比较和分析，包括：

1. 计算匹配得分（优化前和优化后）：
   - 整体匹配得分
   - 技能匹配得分
   - 经验匹配得分
   - 教育匹配得分
2. 分析关键词匹配情况：
   - 优化前简历中与职位描述匹配的关键词数量
   - 优化后简历中与职位描述匹配的关键词数量
   - 新增的与职位描述中关键词匹配的关键词列表（新增的关键词列表中，如果优化前已经存在，则不包含，如果优化后的简历中不存在，则不包含）
3. 比较各技能在优化前后的表现
4. 对比简历各部分的变化：
   - 技能部分的变化
   - 工作经验描述的变化
   - 教育背景的变化
   - 项目经验的变化
5. 总结主要改进点

注意：
- 不要夸大优化效果，必须客观准确的对比两份简历与职位描述的匹配度

你的返回必须是一个有效的JSON对象，符合以下结构：
""" + comparison_schema()
    return system_prompt, user_prompt

def optimize(jd_text=None, resume_text=None):
    try:
        system_prompt, user_prompt = optimize_resume_prompt(jd_text, resume_text)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        optimize_response = get_response_from_llm(messages, model="qwen-qwq-32b", max_tokens=20000, platform="siliconflow")

        current_app.logger.debug(f"optimize_response: {optimize_response}")

        optimize_response = get_json_blocks_from_llm_response(optimize_response)
        if len(optimize_response) < 1:
            raise Exception("No optimization result")

        current_app.logger.debug(f"optimize_response: {optimize_response}")

        optimize_response = json.loads(optimize_response[-1])
        return optimize_response
    except Exception as e:
        current_app.logger.error(f"Error in optimization process: {e}")
        return None

def compare_resumes(original_resume_text, optimized_resume_json, jd_text):
    try:
        optimized_resume_text = json.dumps(optimized_resume_json["optimized_resume"],
                                          ensure_ascii=False, indent=2)

        current_app.logger.debug(f"original_resume_text: {original_resume_text}")
        current_app.logger.debug(f"optimized_resume_text: {optimized_resume_text}")

        system_prompt, user_prompt = compare_resumes_prompt(jd_text, original_resume_text, optimized_resume_text)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        compare_response = get_response_from_llm(messages, model="qwen-qwq-32b", max_tokens=20000, platform="siliconflow")

        current_app.logger.debug(f"compare_response: {compare_response}")

        compare_response = get_json_blocks_from_llm_response(compare_response)
        if len(compare_response) < 1:
            raise Exception("No comparison result")

        compare_response = json.loads(compare_response[-1])
        return compare_response
    except Exception as e:
        current_app.logger.error(f"Error in comparison process: {e}")
        return None

def parse_arguments():
    parser = argparse.ArgumentParser(description='Optimize a resume based on a job description')
    parser.add_argument('--resume_pdf', type=str, help='Path to resume PDF file')
    parser.add_argument('--resume_img', type=str, help='Path to resume image file')
    parser.add_argument('--jd_pdf', type=str, help='Path to job description PDF file')
    parser.add_argument('--jd_img', type=str, help='Path to job description image file')

    return parser.parse_args()

def main():
    args = parse_arguments()

    if not (args.jd_pdf or args.jd_img):
        print("Error: Job description (PDF, image) is required for optimization", file=sys.stderr)
        return 1

    if not args.resume_pdf and not args.resume_img:
        print("Error: Resume (PDF, image) is required for optimization", file=sys.stderr)
        return 1

    if args.jd_pdf and not os.path.exists(args.jd_pdf):
        print("Error: Job description PDF file does not exist", file=sys.stderr)
        return 1

    if args.jd_img and not os.path.exists(args.jd_img):
        print("Error: Job description image file does not exist", file=sys.stderr)
        return 1

    if args.resume_pdf and not os.path.exists(args.resume_pdf):
        print("Error: Resume PDF file does not exist", file=sys.stderr)
        return 1

    if args.resume_img and not os.path.exists(args.resume_img):
        print("Error: Resume image file does not exist", file=sys.stderr)
        return 1

    if args.jd_pdf:
        jd_text = ocr_file(args.jd_pdf)
    elif args.jd_img:
        jd_text = ocr_file(args.jd_img)
    else:
        pass

    if args.resume_pdf:
        resume_text = ocr_file(args.resume_pdf)
    elif args.resume_img:
        resume_text = ocr_file(args.resume_img)
    else:
        pass

    optimized_data = optimize(jd_text, resume_text)
    if not optimized_data:
        print("Error: No optimization result", file=sys.stderr)
        return 1

    comparison_data = compare_resumes(resume_text, optimized_data, jd_text)
    if not comparison_data:
        print("Error: No comparison result", file=sys.stderr)
        return 1

    print(f"优化后的简历: {json.dumps(optimized_data, ensure_ascii=False, indent=2)}")
    print(f"比较结果: {json.dumps(comparison_data, ensure_ascii=False, indent=2)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
