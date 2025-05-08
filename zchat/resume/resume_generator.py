#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from datetime import datetime
import argparse
from pathlib import Path
from flask_babel import gettext as _
from zchat.resume.resume_translations import *

def load_resume_data(file_path):
    """加载简历JSON数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        sys.exit(1)

def format_date_range(start_date, end_date):
    """格式化日期范围"""
    if not start_date:
        return ""

    # 使用翻译常量
    end = end_date if end_date else PRESENT

    return f"{start_date}{DATE_RANGE_SEPARATOR}{end}"

def generate_contact_section(contact):
    """生成联系方式部分"""
    contact_lines = []

    if contact.get("email"):
        contact_lines.append(f"📧 {contact['email']}")
    if contact.get("phone"):
        contact_lines.append(f"📱 {contact['phone']}")
    if contact.get("address"):
        contact_lines.append(f"🏠 {contact['address']}")

    links = []
    if contact.get("linkedin"):
        links.append(f"[{LINKEDIN}]({contact['linkedin']})")
    if contact.get("github"):
        links.append(f"[{GITHUB}]({contact['github']})")
    if contact.get("website"):
        links.append(f"[{PERSONAL_WEBSITE}]({contact['website']})")

    if links:
        contact_lines.append(PIPE_SEPARATOR.join(links))

    return PIPE_SEPARATOR.join(contact_lines)

def generate_personal_info(personal_info):
    """生成个人信息部分"""
    if not personal_info:
        return ""

    sections = []

    # 语言能力
    if personal_info.get("languages") and len(personal_info["languages"]) > 0:
        language_list = [f"{lang['language']} ({lang['proficiency']})" for lang in personal_info["languages"]]
        sections.append(f"{BULLET_POINT}**{LANGUAGES}**{COLON}{COMMA_SEPARATOR.join(language_list)}")

    # 其他个人信息
    if personal_info.get("other_details") and len(personal_info["other_details"]) > 0:
        for detail in personal_info["other_details"]:
            if detail.get("name") and detail.get("value"):
                sections.append(f"{BULLET_POINT}**{detail['name']}**{COLON}{detail['value']}")

    if sections:
        return "\n\n".join(sections)
    return ""

def generate_education_section(education):
    """生成教育经历部分"""
    if not education:
        return ""

    # 使用翻译常量
    sections = [f"## {EDUCATION}\n"]

    for edu in education:
        edu_title = f"**{edu.get('degree', '')}**"
        if edu.get('field_of_study'):
            edu_title += f"{COMMA_SEPARATOR}{edu['field_of_study']}"

        edu_details = []
        edu_details.append(f"*{edu.get('institution', '')}*")

        location_date = []
        if edu.get('location'):
            location_date.append(edu['location'])

        date_range = format_date_range(edu.get('start_date'), edu.get('end_date'))
        if date_range:
            location_date.append(date_range)

        if location_date:
            edu_details.append(f"*{COMMA_SEPARATOR.join(location_date)}*")

        sections.append(f"{edu_title}")
        sections.append(COMMA_SEPARATOR.join(edu_details))

        if edu.get('gpa'):
            sections.append(f"{GPA}{COLON}{edu['gpa']}")

        if edu.get('details'):
            sections.append(f"{edu['details']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_skills_section(skills):
    """生成技能部分"""
    if not skills:
        return ""

    # 使用翻译常量
    sections = [f"## {SKILLS}\n"]

    # 技术技能
    if skills.get("technical") and len(skills["technical"]) > 0:
        sections.append(f"- **{TECHNICAL_SKILLS}**: {', '.join(skills['technical'])}")

    # 软技能
    if skills.get("soft") and len(skills["soft"]) > 0:
        sections.append(f"- **{SOFT_SKILLS}**: {', '.join(skills['soft'])}")

    # 其他技能
    if skills.get("other") and len(skills["other"]) > 0:
        sections.append(f"- **{OTHER_SKILLS}**: {', '.join(skills['other'])}")

    return "\n\n".join(sections) + "\n\n"

def generate_certifications_section(certifications):
    """生成证书部分"""
    if not certifications or len(certifications) == 0:
        return ""

    # Use translation constant
    sections = [f"## {CERTIFICATIONS}\n"]

    for cert in certifications:
        cert_line = f"**{cert.get('name', '')}**"

        details = []
        if cert.get('issuer'):
            details.append(f"{ISSUING_INSTITUTION}{COLON}{cert['issuer']}")

        if cert.get('date'):
            details.append(f"{DATE_OBTAINED}{COLON}{cert['date']}")

        if cert.get('expiration'):
            details.append(f"{EXPIRATION_DATE}{COLON}{cert['expiration']}")

        if cert.get('id'):
            details.append(f"{CERTIFICATE_ID}{COLON}{cert['id']}")

        sections.append(cert_line)

        if details:
            sections.append(COMMA_SEPARATOR.join(details))

        if cert.get('url'):
            sections.append(f"[{VIEW_CERTIFICATE}]({cert['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_experience_section(experience):
    """生成工作经验部分"""
    if not experience or len(experience) == 0:
        return ""

    sections = [f"## {WORK_EXPERIENCE}\n"]

    for exp in experience:
        exp_title = f"**{exp.get('title', '')}** {AT_SYMBOL} *{exp.get('organization', '')}*"
        if exp.get('location'):
            exp_title += f"{COMMA_SEPARATOR}{exp['location']}"

        date_range = format_date_range(exp.get('start_date'), exp.get('end_date'))

        sections.append(f"{exp_title}")
        if date_range:
            sections.append(f"*{date_range}*")

        if exp.get('description'):
            sections.append(f"{exp['description']}")

        # 职责
        if exp.get('responsibilities') and len(exp['responsibilities']) > 0:
            sections.append(f"\n**{RESPONSIBILITIES}{COLON}**")
            for resp in exp['responsibilities']:
                sections.append(f"{BULLET_POINT}{resp}")

        # 成就
        if exp.get('achievements') and len(exp['achievements']) > 0:
            sections.append(f"\n**{ACHIEVEMENTS}{COLON}**")
            for achieve in exp['achievements']:
                sections.append(f"{BULLET_POINT}{achieve}")

        # 技术
        if exp.get('technologies') and len(exp['technologies']) > 0:
            sections.append(f"\n**{TECHNOLOGIES_USED}{COLON}**{COMMA_SEPARATOR.join(exp['technologies'])}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_projects_section(projects):
    """生成项目经验部分"""
    if not projects or len(projects) == 0:
        return ""

    sections = [f"## {PROJECTS}\n"]

    for project in projects:
        project_title = f"**{project.get('name', '')}**"
        if project.get('role'):
            project_title += f" - {project['role']}"

        date_range = format_date_range(project.get('start_date'), project.get('end_date'))

        sections.append(f"{project_title}")
        if date_range:
            sections.append(f"*{date_range}*")

        if project.get('description'):
            sections.append(f"{project['description']}")

        # 技术
        if project.get('technologies') and len(project['technologies']) > 0:
            sections.append(f"**{TECHNOLOGIES}{COLON}**{COMMA_SEPARATOR.join(project['technologies'])}")

        # 成就
        if project.get('achievements') and len(project['achievements']) > 0:
            sections.append(f"**{ACHIEVEMENTS}{COLON}**")
            for achieve in project['achievements']:
                sections.append(f"{BULLET_POINT}{achieve}")

        if project.get('url'):
            sections.append(f"[{PROJECT_LINK}]({project['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_publications_section(publications):
    """生成出版物部分"""
    if not publications or len(publications) == 0:
        return ""

    sections = [f"## {PUBLICATIONS}\n"]

    for pub in publications:
        pub_title = f"**{pub.get('title', '')}**"

        details = []

        if pub.get('authors') and len(pub['authors']) > 0:
            authors_str = COMMA_SEPARATOR.join(pub['authors'])
            details.append(f"{AUTHORS}{COLON}{authors_str}")

        if pub.get('publisher'):
            details.append(f"{PUBLISHER}{COLON}{pub['publisher']}")

        if pub.get('date'):
            details.append(f"{DATE}{COLON}{pub['date']}")

        sections.append(pub_title)

        if details:
            sections.append(COMMA_SEPARATOR.join(details))

        if pub.get('description'):
            sections.append(f"{pub['description']}")

        if pub.get('url'):
            sections.append(f"[{READ_PUBLICATION}]({pub['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_awards_section(awards):
    """生成奖项部分"""
    if not awards or len(awards) == 0:
        return ""

    sections = [f"## {AWARDS}\n"]

    for award in awards:
        award_title = f"**{award.get('name', '')}**"

        details = []
        if award.get('issuer'):
            details.append(f"{ISSUER}{COLON}{award['issuer']}")

        if award.get('date'):
            details.append(f"{DATE}{COLON}{award['date']}")

        sections.append(award_title)

        if details:
            sections.append(COMMA_SEPARATOR.join(details))

        if award.get('description'):
            sections.append(f"{award['description']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_volunteer_section(volunteer_experience):
    """生成志愿者经历部分"""
    if not volunteer_experience or len(volunteer_experience) == 0:
        return ""

    sections = [f"## {VOLUNTEER_EXPERIENCE}\n"]

    for vol in volunteer_experience:
        vol_title = f"**{vol.get('role', '')}** {AT_SYMBOL} *{vol.get('organization', '')}*"

        date_range = format_date_range(vol.get('start_date'), vol.get('end_date'))

        sections.append(vol_title)

        if date_range:
            sections.append(f"*{date_range}*")

        if vol.get('description'):
            sections.append(f"{vol['description']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_personal_sections(data):
    """生成个人评价和兴趣爱好部分"""
    sections = []

    # 自我评价
    if data.get("self_evaluation"):
        sections.append(f"## {SELF_EVALUATION}\n")
        sections.append(data["self_evaluation"])
        sections.append("")  # 添加空行

    # 兴趣爱好
    if data.get("interests") and len(data["interests"]) > 0:
        sections.append(f"## {INTERESTS}\n")
        for interest in data["interests"]:
            sections.append(f"{BULLET_POINT}{interest}")
        sections.append("")  # 添加空行

    # 擅长领域
    if data.get("good_at") and len(data["good_at"]) > 0:
        sections.append(f"## {STRENGTHS}\n")
        for skill in data["good_at"]:
            sections.append(f"{BULLET_POINT}{skill}")
        sections.append("")  # 添加空行

    if sections:
        return "\n".join(sections)
    return ""

def generate_css_for_pdf():
    """生成用于PDF的CSS样式"""
    return """<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}

h1 {
    font-size: 28px;
    text-align: center;
    margin-bottom: 0.5em;
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 10px;
}

h2 {
    font-size: 22px;
    color: #2c3e50;
    margin-top: 25px;
    margin-bottom: 10px;
    padding-bottom: 5px;
    border-bottom: 1px solid #eee;
}

p, li {
    font-size: 14px;
    margin-bottom: 8px;
}

a {
    color: #3498db;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

ul {
    padding-left: 20px;
}

li {
    margin-bottom: 5px;
}

.contact-info {
    text-align: center;
    margin-bottom: 20px;
    font-size: 14px;
}

.date {
    font-style: italic;
    color: #7f8c8d;
}

.section {
    margin-bottom: 20px;
}

.subsection {
    margin-left: 20px;
}

.skill-category {
    font-weight: bold;
    margin-top: 10px;
}

.skill-list {
    margin-left: 20px;
}

@media print {
    body {
        font-size: 12px;
    }

    h1 {
        font-size: 24px;
    }

    h2 {
        font-size: 18px;
    }

    p, li {
        font-size: 12px;
    }
}
</style>"""

def generate_resume_markdown(data, include_css=False):
    """生成完整的简历Markdown"""
    sections = []

    # 添加CSS（如果需要）
    if include_css:
        sections.append(generate_css_for_pdf())

    # 标题（名称）
    if data.get("name"):
        sections.append(f"# {data['name']}")

    # 联系方式
    if data.get("contact"):
        contact_section = generate_contact_section(data["contact"])
        if contact_section:
            sections.append(contact_section)

    # 个人信息
    personal_info_section = generate_personal_info(data.get("personal_info", {}))
    if personal_info_section:
        sections.append(personal_info_section)

    # 个人部分（自我评价、兴趣等）
    personal_sections = generate_personal_sections(data)
    if personal_sections:
        sections.append(personal_sections)

    # 教育经历
    education_section = generate_education_section(data.get("education", []))
    if education_section:
        sections.append(education_section)

    # 技能
    skills_section = generate_skills_section(data.get("skills", {}))
    if skills_section:
        sections.append(skills_section)

    # 工作经验
    experience_section = generate_experience_section(data.get("experience", []))
    if experience_section:
        sections.append(experience_section)

    # 项目经验
    projects_section = generate_projects_section(data.get("projects", []))
    if projects_section:
        sections.append(projects_section)

    # 证书
    certifications_section = generate_certifications_section(data.get("certifications", []))
    if certifications_section:
        sections.append(certifications_section)

    # 出版物
    publications_section = generate_publications_section(data.get("publications", []))
    if publications_section:
        sections.append(publications_section)

    # 奖项
    awards_section = generate_awards_section(data.get("awards", []))
    if awards_section:
        sections.append(awards_section)

    # 志愿者经历
    volunteer_section = generate_volunteer_section(data.get("volunteer_experience", []))
    if volunteer_section:
        sections.append(volunteer_section)

    # 组合所有部分
    footer = f"\n\n---\n*{AUTO_GENERATED}*"

    return "\n\n".join(sections) + footer

def main():
    parser = argparse.ArgumentParser(description='Generate a resume in Markdown format from JSON data.')
    parser.add_argument('input_file', nargs='?', default='resume.json', help='Input JSON file (default: resume.json)')
    parser.add_argument('-o', '--output', help='Output Markdown file (default: <input_filename>.md)')
    parser.add_argument('--no-css', action='store_true', help='Do not include CSS for PDF printing')

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)

    output_path = args.output if args.output else input_path.with_suffix('.md')

    # 加载简历数据
    resume_data = load_resume_data(input_path)

    # 生成Markdown
    markdown_content = generate_resume_markdown(resume_data, args.no_css)

    # 写入文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Resume generated successfully: {output_path}")
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()