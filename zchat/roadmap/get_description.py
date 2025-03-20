import re
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response

system_prompt_template = """
您是一位专业的教育内容开发专家，擅长将复杂概念分解为清晰、全面的解释。

用户正在学习主题「{topic}」，并按照思维导图进行系统性学习。用户已经掌握了思维导图中的上层概念，现在需要深入理解特定的叶子节点概念。

您的任务是：
1. 分析用户提供的思维导图路径 (topic → subtopic → leaf_topic)
2. 对最右侧的叶子概念提供深入、全面的解释
3. 确保解释涵盖该概念的定义、重要性、应用场景和相关技术
4. 提供进阶学习资源建议（书籍、论文、课程等）
5. 将内容组织为结构化的JSON格式

您的解释应当：
- 专业且准确：确保技术细节正确无误
- 深入且全面：覆盖该概念的各个重要方面
- 实用且可操作：包含实际应用指导
- 循序渐进：考虑用户已有的知识基础
- 引用权威资源：推荐高质量的学习材料

请记住，您的解释将直接影响用户对该概念的理解深度和学习效果。
"""

# 使用双花括号 {{ }} 来转义JSON中的花括号，避免与format()方法冲突
user_prompt_template = """
## 思维导图路径
{topic_path}

请对路径中最右侧的叶子概念提供详细解释，帮助我深入理解这个概念。您的解释应包括但不限于：

1. 概念定义与核心原理
2. 历史背景与发展脉络（如适用）
3. 在整体知识体系中的位置与重要性
4. 实际应用场景与案例
5. 常见挑战与解决方案
6. 最佳实践与技巧
7. 与其他相关概念的联系与区别
8. 进阶学习资源推荐（书籍、论文、课程、工具等）

请以JSON格式输出，严格遵循以下schema：

```json
{{
    "type": "object",
    "properties": {{
        "title": {{
            "type": "string",
            "description": "叶子概念的标题"
        }},
        "path": {{
            "type": "array",
            "items": {{
                "type": "string"
            }},
            "description": "从根节点到叶子节点的完整路径"
        }},
        "summary": {{
            "type": "string",
            "description": "概念的简明摘要（100-200字）"
        }},
        "description": {{
            "type": "string",
            "description": "详细解释，包含定义、原理、应用等全面内容"
        }},
        "key_points": {{
            "type": "array",
            "items": {{
                "type": "string"
            }},
            "description": "需要掌握的关键要点列表"
        }},
        "practical_applications": {{
            "type": "array",
            "items": {{
                "type": "object",
                "properties": {{
                    "scenario": {{
                        "type": "string",
                        "description": "应用场景"
                    }},
                    "description": {{
                        "type": "string",
                        "description": "应用描述"
                    }}
                }}
            }},
            "description": "实际应用场景列表"
        }},
        "related_concepts": {{
            "type": "array",
            "items": {{
                "type": "object",
                "properties": {{
                    "concept": {{
                        "type": "string",
                        "description": "相关概念名称"
                    }},
                    "relationship": {{
                        "type": "string",
                        "description": "与主题概念的关系"
                    }}
                }}
            }},
            "description": "相关概念及其与主题的关系"
        }},
        "learning_resources": {{
            "type": "array",
            "items": {{
                "type": "object",
                "properties": {{
                    "type": {{
                        "type": "string",
                        "enum": ["书籍", "论文", "课程", "视频", "工具", "网站", "其他"],
                        "description": "资源类型"
                    }},
                    "title": {{
                        "type": "string",
                        "description": "资源标题"
                    }},
                    "description": {{
                        "type": "string",
                        "description": "资源简介"
                    }},
                    "link": {{
                        "type": "string",
                        "description": "资源链接（如有）"
                    }}
                }}
            }},
            "description": "推荐的学习资源列表"
        }}
    }},
    "required": [
        "title",
        "path",
        "summary",
        "description",
        "key_points",
        "learning_resources"
    ]
}}
```

请确保输出的JSON格式正确，可以直接被解析。不要添加额外的解释或注释。
"""

def get_llm_response(topic, topic_path):
  messages=[
    {"role": "system", "content": system_prompt_template.format(topic=topic)},
    {"role": "user", "content": user_prompt_template.format(topic_path=topic_path)},
  ]
  print(messages)
  # 使用更大的token限制以获取更详细的描述
  response = get_response_from_llm(messages, "qwen-2.5-32b", 8192, platform='aliyun')
  return response

def parse_llm_response(response):
  return get_json_blocks_from_llm_response(response)

def description_from_topic_path(topic, topic_path):
  response = get_llm_response(topic, topic_path)
  json_blocks = parse_llm_response(response)
  if len(json_blocks) == 0:
    return None

  description = json_blocks[0]
  return description


if __name__ == "__main__":
  topic = "UI/UX设计基础"
  topic_path = "前端工程师->设计系统->UI/UX设计基础"
  description = description_from_topic_path(topic, topic_path)
  print(description)
