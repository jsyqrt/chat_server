"""
共享提示词模块，为路径生成提供一致的高质量提示。
"""

# 思维导图 JSON Schema 定义
MINDMAP_JSON_SCHEMA = """
```json
{
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "节点标题"
        },
        "description": {
            "type": "string",
            "description": "节点描述"
        },
        "children": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/node"
            },
            "description": "子节点列表"
        },
        "industry_tag": {
            "type": "string",
            "description": "行业标签, 该思维导图适用于哪个行业，可以为空字符串"
        },
        "job_tag": {
            "type": "string",
            "description": "岗位标签, 该思维导图适用于哪个岗位，可以为空字符串"
        },
        "skill_tag": {
            "type": "string",
            "description": "技能标签, 该思维导图针对哪些技能，用逗号分隔，可以为空字符串"
        }
    },
    "required": [
        "title",
        "description",
        "children",
        "industry_tag",
        "job_tag",
        "skill_tag"
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
"""

# 通用的思维导图生成指南
MINDMAP_GENERATION_GUIDELINES = """
生成思维导图时，请遵循以下指南：

1. 结构化层次：
   - 第一层：10-15个主要主题或知识领域
   - 第二层：每个主题下5-10个子主题
   - 第三层及以下：进一步细分的具体知识点

2. 内容全面性：
   - 技术知识：核心概念、工具、框架、最佳实践
   - 软技能：沟通、团队协作、问题解决能力
   - 职业发展：职业阶段、晋升路径、资质认证
   - 行业知识：行业趋势、标准、法规

3. 逻辑连贯性：
   - 按照学习顺序排列节点
   - 确保知识点之间有清晰的前后依赖关系
   - 从基础到高级的渐进式学习路径

4. 定制化：
   - 根据用户当前水平调整内容深度
   - 针对用户学习目标提供相关重点内容
   - 避免包含用户已掌握的基础知识

5. 完整性：
   - 确保总节点数不少于100个
   - 涵盖所有相关的知识领域和技能
   - 包含实践项目和应用场景

请确保输出的JSON严格遵循提供的Schema，并包含丰富、实用的学习内容。
"""
