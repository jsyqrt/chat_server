#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from datetime import datetime
import argparse
from pathlib import Path

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

    end = end_date if end_date else "至今"
    return f"{start_date} - {end}"

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
        links.append(f"[LinkedIn]({contact['linkedin']})")
    if contact.get("github"):
        links.append(f"[GitHub]({contact['github']})")
    if contact.get("website"):
        links.append(f"[个人网站]({contact['website']})")

    if links:
        contact_lines.append(" | ".join(links))

    return " | ".join(contact_lines)

def generate_personal_info(personal_info):
    """生成个人信息部分"""
    if not personal_info:
        return ""

    sections = []

    # 国籍
    # if personal_info.get("nationality"):
    #     sections.append(f"- **国籍**: {personal_info['nationality']}")

    # 语言能力
    if personal_info.get("languages") and len(personal_info["languages"]) > 0:
        language_list = [f"{lang['language']} ({lang['proficiency']})" for lang in personal_info["languages"]]
        sections.append(f"- **语言能力**: {', '.join(language_list)}")

    # 其他个人信息
    if personal_info.get("other_details") and len(personal_info["other_details"]) > 0:
        for detail in personal_info["other_details"]:
            if detail.get("name") and detail.get("value"):
                sections.append(f"- **{detail['name']}**: {detail['value']}")

    if sections:
        return "\n\n".join(sections)
    return ""

def generate_education_section(education):
    """生成教育经历部分"""
    if not education:
        return ""

    sections = ["## 教育背景\n"]

    for edu in education:
        edu_title = f"**{edu.get('degree', '')}**"
        if edu.get('field_of_study'):
            edu_title += f"，{edu['field_of_study']}"

        edu_details = []
        edu_details.append(f"*{edu.get('institution', '')}*")

        location_date = []
        if edu.get('location'):
            location_date.append(edu['location'])

        date_range = format_date_range(edu.get('start_date'), edu.get('end_date'))
        if date_range:
            location_date.append(date_range)

        if location_date:
            edu_details.append(f"*{', '.join(location_date)}*")

        sections.append(f"{edu_title}")
        sections.append(", ".join(edu_details))

        if edu.get('gpa'):
            sections.append(f"GPA: {edu['gpa']}")

        if edu.get('details'):
            sections.append(f"{edu['details']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_skills_section(skills):
    """生成技能部分"""
    if not skills:
        return ""

    sections = ["## 技能\n"]

    # 技术技能
    if skills.get("technical") and len(skills["technical"]) > 0:
        sections.append(f"- **技术技能**: {', '.join(skills['technical'])}")

    # 软技能
    if skills.get("soft") and len(skills["soft"]) > 0:
        sections.append(f"- **软技能**: {', '.join(skills['soft'])}")

    # 其他技能
    if skills.get("other") and len(skills["other"]) > 0:
        sections.append(f"- **其他技能**: {', '.join(skills['other'])}")

    return "\n\n".join(sections) + "\n\n"

def generate_certifications_section(certifications):
    """生成证书部分"""
    if not certifications or len(certifications) == 0:
        return ""

    sections = ["## 证书\n"]

    for cert in certifications:
        cert_line = f"**{cert.get('name', '')}**"

        details = []
        if cert.get('issuer'):
            details.append(f"颁发机构: {cert['issuer']}")
        if cert.get('date'):
            details.append(f"获得日期: {cert['date']}")
        if cert.get('expiration'):
            details.append(f"到期日期: {cert['expiration']}")
        if cert.get('id'):
            details.append(f"证书ID: {cert['id']}")

        sections.append(cert_line)

        if details:
            sections.append(", ".join(details))

        if cert.get('url'):
            sections.append(f"[查看证书]({cert['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_experience_section(experience):
    """生成工作经验部分"""
    if not experience or len(experience) == 0:
        return ""

    sections = ["## 工作经验\n"]

    for exp in experience:
        exp_title = f"**{exp.get('title', '')}** @ *{exp.get('organization', '')}*"
        if exp.get('location'):
            exp_title += f", {exp['location']}"

        date_range = format_date_range(exp.get('start_date'), exp.get('end_date'))

        sections.append(f"{exp_title}")
        if date_range:
            sections.append(f"*{date_range}*")

        if exp.get('description'):
            sections.append(f"{exp['description']}")

        # 职责
        if exp.get('responsibilities') and len(exp['responsibilities']) > 0:
            sections.append("\n**职责:**")
            for resp in exp['responsibilities']:
                sections.append(f"- {resp}")

        # 成就
        if exp.get('achievements') and len(exp['achievements']) > 0:
            sections.append("\n**成就:**")
            for achieve in exp['achievements']:
                sections.append(f"- {achieve}")

        # 技术
        if exp.get('technologies') and len(exp['technologies']) > 0:
            sections.append(f"\n**使用技术:** {', '.join(exp['technologies'])}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_projects_section(projects):
    """生成项目经验部分"""
    if not projects or len(projects) == 0:
        return ""

    sections = ["## 项目经验\n"]

    for proj in projects:
        proj_title = f"**{proj.get('name', '')}**"
        if proj.get('role'):
            proj_title += f" - {proj['role']}"

        date_range = format_date_range(proj.get('start_date'), proj.get('end_date'))

        sections.append(f"{proj_title}")
        if date_range:
            sections.append(f"*{date_range}*")

        if proj.get('description'):
            sections.append(f"{proj['description']}")

        # 技术
        if proj.get('technologies') and len(proj['technologies']) > 0:
            sections.append(f"\n**使用技术:** {', '.join(proj['technologies'])}")

        # 成就
        if proj.get('achievements') and len(proj['achievements']) > 0:
            sections.append("\n**成就:**")
            for achieve in proj['achievements']:
                sections.append(f"- {achieve}")

        if proj.get('url'):
            sections.append(f"\n[项目链接]({proj['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_publications_section(publications):
    """生成出版物部分"""
    if not publications or len(publications) == 0:
        return ""

    sections = ["## 出版物\n"]

    for pub in publications:
        pub_title = f"**{pub.get('title', '')}**"

        details = []
        if pub.get('authors') and len(pub['authors']) > 0:
            authors = ", ".join(pub['authors'])
            details.append(f"作者: {authors}")

        if pub.get('publisher'):
            details.append(f"发表于: {pub['publisher']}")

        if pub.get('date'):
            details.append(f"出版日期: {pub['date']}")

        sections.append(pub_title)

        if details:
            sections.append(", ".join(details))

        if pub.get('description'):
            sections.append(f"{pub['description']}")

        if pub.get('url'):
            sections.append(f"[查看出版物]({pub['url']})")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_awards_section(awards):
    """生成奖项部分"""
    if not awards or len(awards) == 0:
        return ""

    sections = ["## 奖项荣誉\n"]

    for award in awards:
        award_title = f"**{award.get('name', '')}**"

        details = []
        if award.get('issuer'):
            details.append(f"颁发机构: {award['issuer']}")

        if award.get('date'):
            details.append(f"获奖日期: {award['date']}")

        sections.append(award_title)

        if details:
            sections.append(", ".join(details))

        if award.get('description'):
            sections.append(f"{award['description']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_volunteer_section(volunteer_experience):
    """生成志愿者经历部分"""
    if not volunteer_experience or len(volunteer_experience) == 0:
        return ""

    sections = ["## 志愿者经历\n"]

    for vol in volunteer_experience:
        vol_title = f"**{vol.get('role', '')}** @ *{vol.get('organization', '')}*"

        date_range = format_date_range(vol.get('start_date'), vol.get('end_date'))

        sections.append(vol_title)
        if date_range:
            sections.append(f"*{date_range}*")

        if vol.get('description'):
            sections.append(f"{vol['description']}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_personal_sections(data):
    """生成个人评价、兴趣爱好等部分"""
    sections = []

    # 自我评价
    if data.get("self_evaluation"):
        sections.append("## 自我评价\n")
        sections.append(f"{data['self_evaluation']}\n")

    # 特长与兴趣
    if (data.get("good_at") and len(data["good_at"]) > 0) or \
       (data.get("interests") and len(data["interests"]) > 0) or \
       (data.get("weak_point") and len(data["weak_point"]) > 0):

        sections.append("## 个人特点\n")

        if data.get("good_at") and len(data["good_at"]) > 0:
            sections.append(f"**特长**: {', '.join(data['good_at'])}")

        if data.get("interests") and len(data["interests"]) > 0:
            sections.append(f"**兴趣爱好**: {', '.join(data['interests'])}")

        # if data.get("weak_point") and len(data["weak_point"]) > 0:
            # sections.append(f"**待改进**: {', '.join(data['weak_point'])}")

        sections.append("")  # 添加空行

    return "\n\n".join(sections)

def generate_css_for_pdf():
    """生成适合PDF打印的CSS样式"""
    return """
<style>
@media print {
    @page {
        size: A4;
        margin: 1.5cm;
    }

    body {
        font-family: 'Noto Sans SC', 'Arial', sans-serif;
        font-size: 10pt;
        line-height: 1.4;
        color: #333;
    }

    h1 {
        font-size: 18pt;
        margin-bottom: 0.3cm;
        color: #2c3e50;
    }

    h2 {
        font-size: 14pt;
        margin-top: 0.7cm;
        margin-bottom: 0.3cm;
        color: #3498db;
        border-bottom: 1px solid #3498db;
        padding-bottom: 0.1cm;
    }

    a {
        color: #2980b9;
        text-decoration: none;
    }

    ul {
        padding-left: 0.5cm;
    }

    li {
        margin-bottom: 0.2cm;
    }

    p {
        margin-top: 0.1cm;
        margin-bottom: 0.2cm;
    }
}
</style>
"""

def generate_resume_markdown(data, include_css=False):
    """生成完整的简历Markdown"""
    sections = []

    # 标题和联系方式
    sections.append(f"# {data.get('name', '简历')}\n")
    sections.append(generate_contact_section(data.get('contact', {})))
    sections.append("")  # 添加空行

    # 个人信息
    personal_info = generate_personal_info(data.get('personal_info', {}))
    if personal_info:
        sections.append(personal_info)
        sections.append("")  # 添加空行

    # 自我评价和个人特点
    personal_sections = generate_personal_sections(data)
    if personal_sections:
        sections.append(personal_sections)

    # 教育背景
    education_section = generate_education_section(data.get('education', []))
    if education_section:
        sections.append(education_section)

    # 技能
    skills_section = generate_skills_section(data.get('skills', {}))
    if skills_section:
        sections.append(skills_section)

    # 工作经验
    experience_section = generate_experience_section(data.get('experience', []))
    if experience_section:
        sections.append(experience_section)

    # 项目经验
    projects_section = generate_projects_section(data.get('projects', []))
    if projects_section:
        sections.append(projects_section)

    # 证书
    certifications_section = generate_certifications_section(data.get('certifications', []))
    if certifications_section:
        sections.append(certifications_section)

    # 出版物
    publications_section = generate_publications_section(data.get('publications', []))
    if publications_section:
        sections.append(publications_section)

    # 奖项
    awards_section = generate_awards_section(data.get('awards', []))
    if awards_section:
        sections.append(awards_section)

    # 志愿者经历
    volunteer_section = generate_volunteer_section(data.get('volunteer_experience', []))
    if volunteer_section:
        sections.append(volunteer_section)

    # 添加CSS (如果需要)
    if include_css:
        sections.append(generate_css_for_pdf())

    return "\n\n".join(sections)

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