import os
import json
import uuid
import time
import random
from enum import Enum

from flask import request, current_app, Blueprint, jsonify, Response, stream_with_context, g
from werkzeug.utils import secure_filename

from zchat.auth import login_required, current_user, admin_required
from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.roadmap import RoadmapOps, RoadmapInteractionOps, RoadmapStatus
from zchat.roadmap.from_jd import mindmap_from_jd_and_resume
from zchat.roadmap.from_topic import mindmap_from_topic
from zchat.roadmap.get_description import description_from_topic_path, description_from_topic_path_stream
from zchat.nosql import *
from zchat.apis.ocr import ocr_file
from zchat.models.points import ServiceType
from zchat.points import check_points_sufficient, consume_points_for_service

bp = Blueprint('roadmap', __name__, url_prefix='/roadmap')

# Get user language (one-line function)
def get_user_lang():
    current_app.logger.debug(f"g.lang: {g.lang}")
    return getattr(g, 'lang', 'zh_CN')

# Dictionary for translations
TRANSLATIONS = {
    'zh_CN': {
        'no_jd_id': '未提供JD ID',
        'jd_not_found': '找不到对应的JD: {jd_id}',
        'no_jd_text': '提供的JD ID没有JD内容: {jd_id}',
        'failed_create_mindmap': '创建思维导图失败',
        'custom_career_path': '定制专属职业成长路径',
        'create_roadmap_desc': '创建学习路径({title})',
        'points_deduction_failed': '积分扣除失败，请稍后重试',
        'no_json_file': '未提供JSON文件',
        'description_not_found': '学习状态未找到',
        'stages': '{count}个阶段',
        'core_skills': '{count}个核心技能',
        'resources_count': '{count}个资源',
        'resources_plus': '{count}+资源',
        'stats_format': '{stages} · {skills}{resources}',
        'get_knowledge_detail': '获取知识详情({topic})',
        'unlock_roadmap': '解锁学习路径({title})',
        'roadmap_not_found': '找不到对应的学习路径',
        'official_roadmaps_reset': '官方学习路径已重置',
        'update_submitted': '更新已提交',
        'missing_required_fields': '缺少必填字段',
        'invalid_status_format': '状态格式无效',
        'learning_status_submitted': '学习状态已成功提交',
        'learning_status_not_found': '找不到学习状态',
        'index_deleted': '索引已删除'
    },
    'en': {
        'no_jd_id': 'No JD ID provided',
        'jd_not_found': 'JD not found for the given JD ID: {jd_id}',
        'no_jd_text': 'No JD provided for the given JD ID: {jd_id}',
        'failed_create_mindmap': 'Failed to create mindmap',
        'custom_career_path': 'Customize your career growth path',
        'create_roadmap_desc': 'Create learning path ({title})',
        'points_deduction_failed': 'Points deduction failed, please try again later',
        'no_json_file': 'No JSON file provided',
        'description_not_found': 'Learning status not found',
        'stages': '{count} stages',
        'core_skills': '{count} core skills',
        'resources_count': '{count} resources',
        'resources_plus': '{count}+ resources',
        'stats_format': '{stages} · {skills}{resources}',
        'get_knowledge_detail': 'Get knowledge details ({topic})',
        'unlock_roadmap': 'Unlock learning path ({title})',
        'roadmap_not_found': 'Roadmap not found',
        'official_roadmaps_reset': 'Official roadmaps reset',
        'update_submitted': 'Update submitted',
        'missing_required_fields': 'Missing required fields',
        'invalid_status_format': 'Invalid status format',
        'learning_status_submitted': 'Learning status submitted successfully',
        'learning_status_not_found': 'Learning status not found',
        'index_deleted': 'Index deleted'
    }
}

# Translation function
def translate(key, lang='zh_CN', **kwargs):
    """Translate a key based on language with optional format parameters"""

    if not lang or lang not in TRANSLATIONS:
        lang = 'zh_CN'  # Default to Chinese

    translation = TRANSLATIONS[lang].get(key, TRANSLATIONS['zh_CN'].get(key, key))
    if kwargs:
        return translation.format(**kwargs)
    return translation

# Quotes for different languages
QUOTES = {
    'zh_CN': [
        "学过的技能，是未来的底气",
        "知识如光，照亮职场每一步",
        "今日埋头充电，明日抬头领跑",
        "坚持的人，终将抵达梦想的终点站",
        "键盘敲出未来，代码编织梦想",
        "秒针不停，学习不止，时间看得见",
        "每天进步1%，一年强大37倍",
        "低谷时蓄力，巅峰时从容",
        "职场长跑，学习是永不停歇的补给站",
        "重复千万遍，匠魂自然现",
        "证书是水到渠成，不是终点",
        "翻越舒适区，方见星辰大海",
        "此刻的笔记，是明日的铠甲",
        "困倦时多学5分钟，命运改道中",
        "把知识磨成利剑，职场所向披靡",
        "屏幕前的深夜，终将兑换成光芒",
        "每个知识点，都是未来的垫脚石",
        "学如登山，坚持者俯瞰云端",
        "今天的枯燥，是未来的游刃有余",
        "把\"我不会\"变成\"我刚学会\"",
        "技能存折，每日存入未来利息",
        "熬过无人问津，掌声自然轰鸣",
        "职场没有白走的路，步步都算数",
        "专注当下，让时间复利成长",
        "三分钟热度，也能点燃人生",
        "学海无涯，此刻即是最好的岸",
        "别人追剧时，你在追赶人生",
        "碎片时间拼图，终成事业版图",
        "抱怨内卷不如磨砺锋芒",
        "每个深夜的屏幕，都在雕刻未来",
        "学得越痛，成长越狠",
        "停止学习才是真正的瓶颈期",
        "把焦虑转化为具体的学习动作",
        "笨功夫里藏着最聪明的捷径",
        "职场没有奇迹，只有累积轨迹",
        "把证书当副产品，成长才是正收益",
        "耐心浇灌，静待职场开花",
        "学如氧气，时刻储备才能自由呼吸",
        "低谷期是上帝给的进修时间",
        "每个技能点，都在拓宽人生半径",
        "别等机会敲门，先把自己武装到门框",
        "今天的枯燥代码，明天的自由密钥",
        "学习像竹子，四年扎根一朝破土",
        "让知识迭代速度超过年龄增长",
        "把\"我试试\"变成\"我擅长\"",
        "职场如战场，学习是终身防弹衣",
        "熬过平台期，迎来指数级跃升",
        "在别人躺平时，悄悄重塑竞争力",
        "每个知识点都在增加人生选项",
        "学习是最不会背叛你的投资",
    ],
    'en': [
        "Skills learned are future confidence",
        "Knowledge is light, guiding every career step",
        "Head down charging today, head up leading tomorrow",
        "The persistent will reach their destination",
        "Future typed on keyboards, dreams woven in code",
        "Time ticks, learning continues, progress visible",
        "Improve 1% daily, grow 37x yearly",
        "Build strength in valleys, remain calm at peaks",
        "Career is a marathon, learning is the endless supply station",
        "Mastery comes through repetition",
        "Certificates are milestones, not destinations",
        "Beyond comfort zones lie stars and oceans",
        "Today's notes are tomorrow's armor",
        "Five more minutes when tired changes destiny's path",
        "Sharpen knowledge into swords, conquer every challenge",
        "Late nights at screens transform into future brilliance",
        "Each knowledge point is a stepping stone to your future",
        "Learning is like climbing mountains - persist to see above clouds",
        "Today's tedium is tomorrow's excellence",
        "Transform \"I don't know\" into \"I just learned\"",
        "Skills are savings with future interest",
        "Endure obscurity, applause will follow",
        "No wasted steps in careers, everything counts",
        "Focus on now, let time compound growth",
        "Even brief enthusiasm can ignite life",
        "In the endless learning sea, now is the best shore",
        "While others chase shows, you chase your life",
        "Fragments of time build your career map",
        "Don't complain about competition, sharpen your edge",
        "Every night screen carves your future",
        "Greater learning pain, greater growth",
        "The real plateau is when you stop learning",
        "Convert anxiety to concrete learning actions",
        "Slow methods hide the smartest shortcuts",
        "No miracles in careers, only accumulated trajectories",
        "Certificates are byproducts, growth is the real gain",
        "Water patiently, wait for career blooms",
        "Learning is oxygen, reserve it for freedom to breathe",
        "Valleys are God-given upgrade times",
        "Each skill point expands your life radius",
        "Don't wait for opportunity to knock, arm yourself now",
        "Today's tedious code, tomorrow's freedom key",
        "Learning is like bamboo, four years of roots before breaking ground",
        "Let knowledge update faster than age growth",
        "Turn \"let me try\" into \"I excel at this\"",
        "Career is battlefield, learning is lifelong armor",
        "Endure plateaus for exponential leaps",
        "Rebuild competitiveness while others rest",
        "Every knowledge point adds life options",
        "Learning is investment that never betrays you",
    ]
}

class RoadmapType(Enum):
    OFFICIAL = 'official'
    USER = 'user'

class RoadmapKind(Enum):
    INDUSTRY = 'industry'
    JOB = 'job'
    SKILL = 'skill'
    SKILL_GROUP = 'skill_group'
    TOPIC = 'topic'

    @staticmethod
    def from_string(kind_str):
        if kind_str == 'industry':
            return RoadmapKind.INDUSTRY
        elif kind_str == 'job':
            return RoadmapKind.JOB
        elif kind_str == 'skill':
            return RoadmapKind.SKILL
        elif kind_str == 'skill_group':
            return RoadmapKind.SKILL_GROUP
        elif kind_str == 'topic':
            return RoadmapKind.TOPIC
        else:
            raise ValueError(f"Invalid roadmap kind: {kind_str}")

class MindmapModifier:
    def __init__(self):
        self.id_counter = 0

    def generate_id(self):
        # self.id_counter += 1
        # return self.id_counter
        return str(uuid.uuid4())

    def generate_from_file(self, mindmap_path):
        with open(mindmap_path, 'r') as f:
            mindmap = json.load(f)
        return self.generate(mindmap)

    def generate(self, mindmap):
        updated_mindmap = self.generate_for_map(mindmap)
        return updated_mindmap

    def generate_for_map(self, map):
        updated_map = map
        updated_map['id'] = self.generate_id()
        # updated_map['description'] = map.get('title')
        # updated_map['done'] = random.random() > 0.7

        children = map.get('children', [])
        if children:
            new_children = []
            for item in children:
                if isinstance(item, dict):
                    new_children.append(self.generate_for_map(item))
            updated_map['children'] = new_children

        return updated_map


@bp.route('/create_from_jd_and_resume', methods=['POST'])
@login_required
def create_from_jd_and_resume():
    jd_id = request.form.get('jd_id', None)
    if not jd_id:
        lang = get_user_lang()
        return jsonify({'error': translate('no_jd_id', lang)}), 400

    user_id = current_user.get_id_int()

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.CREATE_ROADMAP.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    # 获取用户语言
    lang = get_user_lang()

    resume_file = request.files.get('resume_file', None)
    resume_file_name = request.form.get('resume_file_name', None)

    jd_record = get_jd_record_nosql(current_app, user_id, jd_id)
    if not jd_record:
        return jsonify({'error': translate('jd_not_found', lang, jd_id=jd_id)}), 400

    jd = jd_record.get('jd_text', '')
    if not jd:
        return jsonify({'error': translate('no_jd_text', lang, jd_id=jd_id)}), 400

    file_records = {}

    if resume_file:
        filename = secure_filename(resume_file.filename)
        filename = f'{uuid.uuid4()}_{filename}'
        dir_path = os.path.join(current_app.instance_path, 'resumes')
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_records['resume_files'] = [
            {
                'filename': resume_file.filename,
                'path': f'/resumes/{filename}',
            }
        ]
        file_path = os.path.join(dir_path, filename)
        resume_file.save(file_path)
        resume = ocr_file(file_path)
    elif resume_file_name:
        old_file_records = get_file_records_nosql(current_app, user_id)
        file_path = None
        if old_file_records:
            for resume_file in old_file_records.get('resume_files', []):
                if resume_file['filename'] == resume_file_name:
                    file_path = resume_file['path']
                    break
        if file_path:
            full_file_path = f"{current_app.instance_path}/{file_path}"
            resume = ocr_file(full_file_path)
        else:
            resume = ''
    else:
        resume = ''

    current_app.logger.debug(f"received jd text: {jd}, resume text: {resume}")

    if len(file_records.keys()) > 0:
        file_records['id'] = user_id
        file_records['user_id'] = user_id
        old_file_records = get_file_records_nosql(current_app, user_id)
        if old_file_records:
            old_file_records['resume_files'] = old_file_records.get('resume_files', []) + file_records['resume_files']
            add_file_records_nosql(current_app, old_file_records)

    mindmap_json = mindmap_from_jd_and_resume(jd, resume, lang)

    current_app.logger.debug(f"got mindmap json: {mindmap_json}")

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            mindmap_info = json.loads(mindmap_json)
            is_valid = True
        except Exception as e:
            # try again
            mindmap_json = mindmap_from_jd_and_resume(jd, resume, lang)
            max_retries -= 1

    if not mindmap_info:
        return jsonify({'error': translate('failed_create_mindmap', lang)}), 400

    mindmap_id_generator = MindmapModifier()
    mindmap = mindmap_id_generator.generate(mindmap_info)
    mindmap['roadmap_id'] = str(uuid.uuid4())
    mindmap['created_by'] = user_id
    mindmap['created_at'] = time.time()
    mindmap['updated_at'] = time.time()
    mindmap['jd_id'] = jd_id

    roadmap_id = mindmap['roadmap_id']
    # https://emojipedia.org/people
    roadmap_icon = '🧑‍💻'
    roadmap_title = mindmap['title']
    roadmap_subtitle = translate('custom_career_path', lang)
    roadmap_type = RoadmapType.USER.value
    roadmap_kind = RoadmapKind.JOB.value
    roadmap_status = RoadmapStatus.PRIVATE.value
    roadmap_lang = lang
    mindmap_id = mindmap['id']
    created_by = user_id
    industry_tag = mindmap['industry_tag']
    job_tag = mindmap['job_tag']
    skill_tag = mindmap['skill_tag']

    roadmap_ops = RoadmapOps(db.session)
    roadmap = roadmap_ops.create_roadmap(
        id=roadmap_id,
        icon=roadmap_icon,
        title=roadmap_title,
        subtitle=roadmap_subtitle,
        type=roadmap_type,
        kind=roadmap_kind,
        status=roadmap_status,
        lang=roadmap_lang,
        mindmap_id=mindmap_id,
        created_by=created_by,
        industry_tag=industry_tag,
        job_tag=job_tag,
        skill_tag=skill_tag,
    )

    add_mindmap_nosql(current_app, mindmap)

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.CREATE_ROADMAP.value, translate('create_roadmap_desc', lang, title=roadmap.roadmap_title))
    if not success:
        return jsonify({'error': translate('points_deduction_failed', lang), 'points_required': True}), 402

    return jsonify({
        'participants': 0,
        'completions': 0,
        'favorites': 0,
        'shares': 0,
        'id': roadmap.roadmap_id,
        'icon': roadmap.roadmap_icon,
        'title': roadmap.roadmap_title,
        'subtitle': roadmap.roadmap_subtitle,
        'type': roadmap.roadmap_type,
        'kind': roadmap.roadmap_kind,
        'lang': roadmap.roadmap_lang,
        'mindmap': mindmap,
        'points_spent': points_spent
    })

@bp.route('/dump_all_roadmaps', methods=['GET'])
@login_required
@admin_required
def dump_all_roadmaps():
    roadmap_ops = RoadmapOps(db.session)
    roadmaps = roadmap_ops.get_all_roadmaps()
    for roadmap in roadmaps:
        mindmap = get_mindmap_nosql(current_app, roadmap['mindmap_id'])
        roadmap['mindmap'] = mindmap
    return jsonify({
        'roadmaps': roadmaps,
    })

@bp.route('/restore_all_roadmaps', methods=['POST'])
@login_required
@admin_required
def restore_all_roadmaps():
    json_file = request.files.get('json_file')
    lang = get_user_lang()

    if not json_file:
        return jsonify({'error': translate('no_json_file', lang)}), 400

    roadmap_ops = RoadmapOps(db.session)
    roadmaps = json.load(json_file)
    for roadmap in roadmaps['roadmaps']:
        roadmap_ops.delete_roadmap(roadmap['id'])
        roadmap_ops.create_roadmap(
            id=roadmap['id'],
            icon=roadmap['icon'],
            title=roadmap['title'],
            subtitle=roadmap['subtitle'],
            type=roadmap['type'],
            kind=roadmap['kind'],
            status=roadmap['status'],
            lang=roadmap['lang'],
            mindmap_id=roadmap['mindmap_id'],
            created_by=roadmap['created_by'],
            industry_tag=roadmap['industry_tag'],
            job_tag=roadmap['job_tag'],
            skill_tag=roadmap['skill_tag'],
        )
        add_mindmap_nosql(current_app, roadmap['mindmap'])
    return jsonify({
        'success': True,
    })

@bp.route('/create_from_topic', methods=['POST'])
@login_required
def create_from_topic():
    topic = request.form.get('topic')
    kind = request.form.get('kind')
    skill_level = request.form.get('skill_level')
    learning_goal = request.form.get('learning_goal', '')
    user_background = request.form.get('user_background', '')
    other_prompts = request.form.get('other_prompts', '')
    user_id = current_user.get_id_int()

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.CREATE_ROADMAP.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    # 获取用户语言
    lang = get_user_lang()

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            mindmap = mindmap_from_topic(topic, kind, skill_level, learning_goal, user_background, other_prompts, lang)
            if mindmap:
                mindmap = json.loads(mindmap)
                is_valid = True
        except Exception as e:
            # try again
            mindmap = mindmap_from_topic(topic, kind, skill_level, learning_goal, user_background, other_prompts, lang)
            max_retries -= 1

    if not mindmap:
        return jsonify({'error': 'Failed to create mindmap'}), 400

    mindmap_id_generator = MindmapModifier()
    mindmap = mindmap_id_generator.generate(mindmap)
    mindmap['roadmap_id'] = str(uuid.uuid4())
    mindmap['created_by'] = user_id
    mindmap['created_at'] = time.time()
    mindmap['updated_at'] = time.time()

    roadmap_id = mindmap['roadmap_id']
    # https://emojipedia.org/people
    roadmap_icon = '🧑‍💻'
    roadmap_title = topic
    roadmap_subtitle = learning_goal
    roadmap_type = RoadmapType.USER.value
    roadmap_lang = lang
    roadmap_kind = RoadmapKind.from_string(kind)
    roadmap_status = RoadmapStatus.PUBLIC.value
    mindmap_id = mindmap['id']
    industry_tag = mindmap['industry_tag']
    job_tag = mindmap['job_tag']
    skill_tag = mindmap['skill_tag']
    created_by = user_id

    roadmap_ops = RoadmapOps(db.session)
    roadmap = roadmap_ops.create_roadmap(
        id=roadmap_id,
        icon=roadmap_icon,
        title=roadmap_title,
        subtitle=roadmap_subtitle,
        type=roadmap_type,
        kind=roadmap_kind,
        status=roadmap_status,
        lang=roadmap_lang,
        mindmap_id=mindmap_id,
        created_by=created_by,
        industry_tag=industry_tag,
        job_tag=job_tag,
        skill_tag=skill_tag,
    )

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.CREATE_ROADMAP.value, translate('create_roadmap_desc', lang, title=topic))
    if not success:
        return jsonify({'error': translate('points_deduction_failed', lang), 'points_required': True}), 402

    add_mindmap_nosql(current_app, mindmap)

    return jsonify({
        'participants': 0,
        'completions': 0,
        'favorites': 0,
        'shares': 0,
        'id': roadmap.roadmap_id,
        'icon': roadmap.roadmap_icon,
        'title': roadmap.roadmap_title,
        'subtitle': roadmap.roadmap_subtitle,
        'type': roadmap.roadmap_type,
        'kind': roadmap.roadmap_kind,
        'lang': roadmap.roadmap_lang,
        'mindmap': mindmap,
        'points_spent': points_spent
    })

@bp.route('/industry_tags', methods=['GET'])
# @login_required
def industry_tags():
    roadmap_ops = RoadmapOps(db.session)
    lang = get_user_lang()
    industry_tags = roadmap_ops.all_industry_tags(lang)
    return jsonify({
        'industry_tags': industry_tags,
    })

@bp.route('/job_tags_of_industry_tags', methods=['GET'])
# @login_required
def job_tags_of_industry_tags():
    industry_tags = request.args.get('industry_tags')
    industry_tags = industry_tags.split(',')
    roadmap_ops = RoadmapOps(db.session)
    lang = get_user_lang()
    job_tags = []
    for industry_tag in industry_tags:
        job_tags.extend(roadmap_ops.job_tags_of_industry_tag(industry_tag, lang))
    return jsonify({
        'job_tags': job_tags,
    })

@bp.route('/skill_tags_of_job_tags', methods=['GET'])
# @login_required
def skill_tags_of_job_tags():
    job_tags = request.args.get('job_tags')
    job_tags = job_tags.split(',')
    roadmap_ops = RoadmapOps(db.session)
    lang = get_user_lang()
    skill_tags = []
    for job_tag in job_tags:
        skill_tags.extend(roadmap_ops.skill_tags_of_job_tag(job_tag, lang))
    return jsonify({
        'skill_tags': skill_tags,
    })

@bp.route('/search_topic', methods=['POST'])
@login_required
def search_topic():
    topics = request.form.get('topics')
    topics = topics.split(',')
    offset = int(request.form.get('offset', '0'))
    limit = int(request.form.get('limit', '10'))
    lang = get_user_lang()

    current_app.logger.debug(f"search_topic: {topics}, offset: {offset}, limit: {limit}")

    roadmap_ops = RoadmapOps(db.session)
    roadmaps = roadmap_ops.search_roadmaps_for_topics(topics, lang, offset, limit)
    for roadmap in roadmaps:
        mindmap = get_mindmap_nosql(current_app, roadmap['mindmap_id'])
        roadmap['description'] = mindmap['description']
        roadmap['subtitle'] = stats_of_mindmap(mindmap)
        roadmap['total_stages'] = len(mindmap.get('children', []))

    return jsonify(roadmaps)

@bp.route('/hot_roadmaps', methods=['POST'])
@login_required
def hot_roadmaps():
    roadmap_kind = request.form.get('roadmap_kind', RoadmapKind.JOB.value)
    order_by = request.form.get('order_by', 'participanted')
    offset = int(request.form.get('offset', '0'))
    limit = int(request.form.get('limit', '10'))
    lang = get_user_lang()

    roadmap_ops = RoadmapOps(db.session)
    roadmaps = roadmap_ops.get_hot_roadmaps(roadmap_kind, order_by, lang, offset, limit)
    for roadmap in roadmaps:
        mindmap = get_mindmap_nosql(current_app, roadmap['mindmap_id'])
        roadmap['description'] = mindmap['description']
        roadmap['subtitle'] = stats_of_mindmap(mindmap)
        roadmap['total_stages'] = len(mindmap.get('children', []))

    return jsonify(roadmaps)

@bp.route('/my_roadmaps', methods=['GET'])
@login_required
def my_roadmaps():
    user_id = current_user.get_id_int()
    offset = int(request.args.get('offset', '0'))
    limit = int(request.args.get('limit', '10'))

    roadmap_ops = RoadmapOps(db.session)
    roadmaps = roadmap_ops.get_roadmaps_by_user_id(user_id, offset, limit)
    count = roadmap_ops.get_roadmaps_count_by_user_id(user_id)
    for roadmap in roadmaps:
        mindmap = get_mindmap_nosql(current_app, roadmap['mindmap_id'])
        if mindmap:
            roadmap['subtitle'] = stats_of_mindmap(mindmap)
            roadmap['description'] = mindmap['description']
            roadmap['total_stages'] = len(mindmap.get('children', []))
        else:
            current_app.logger.error(f"mindmap not found: {roadmap['mindmap_id']}, mindmap: {mindmap}")
            roadmap['subtitle'] = ''
            roadmap['description'] = ''
            roadmap['total_stages'] = 0

    return jsonify({
        'roadmaps': roadmaps,
        'count': count,
    })

@bp.route('/description_stream', methods=['POST'])
@login_required
def description_stream():
    topic = request.form.get('topic')
    topic_path = request.form.get('topic_path')
    topic_path = topic_path.split(',')
    user_id = current_user.get_id_int()
    lang = request.form.get('lang')

    current_app.logger.debug(f"description_stream topic: {topic}, topic_path: {topic_path}")

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.GET_DESCRIPTION.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.GET_DESCRIPTION.value, translate('get_knowledge_detail', lang, topic=topic))
    if not success:
        return jsonify({'error': translate('points_deduction_failed', lang), 'points_required': True}), 402

    def generate():
        for chunk in description_from_topic_path_stream(topic, topic_path, lang):
            yield chunk

    return Response(stream_with_context(generate()), mimetype='text/plain')

# ------------------------------------------------------------

def stats_of_mindmap(mindmap):
    lang = get_user_lang()

    num_stages = len(mindmap.get('children', []))
    num_skills = 0
    for stage in mindmap.get('children', []):
        num_skills += len(stage.get('children', []))

    num_resources = 0
    for stage in mindmap.get('children', []):
        for skill in stage.get('children', []):
            num_resources += len(skill.get('links', []))

    stages_text = translate('stages', lang, count=num_stages)
    skills_text = translate('core_skills', lang, count=num_skills)

    resources_str = ''
    if num_resources > 10:
        resources_str = ' · ' + translate('resources_plus', lang, count=num_resources//10*10)
    elif num_resources > 0:
        resources_str = ' · ' + translate('resources_count', lang, count=num_resources)

    return f'{stages_text} · {skills_text}{resources_str}'

@bp.route('/official_maps', methods=['GET'])
@login_required
def official_maps():
    lang = get_user_lang()
    roadmap_ops = RoadmapOps(db.session)
    official_roadmaps = roadmap_ops.get_official_roadmaps(lang)
    for item in official_roadmaps:
        mindmap = get_mindmap_nosql(current_app, item['mindmap_id'])
        item['subtitle'] = stats_of_mindmap(mindmap)
        item['description'] = mindmap['description']
        item['total_stages'] = len(mindmap.get('children', []))

    return jsonify(official_roadmaps)

@bp.route('/map', methods=['GET'])
@login_required
def get_map():
    id = request.args.get('id')
    with_mindmap = request.args.get('with_mindmap', 'false') == 'true'
    lang = get_user_lang()

    roadmap_ops = RoadmapOps(db.session)
    roadmap = roadmap_ops.get_roadmap(id)
    if roadmap:

        # 检查是否已解锁
        interaction_ops = RoadmapInteractionOps(db.session)
        viewed = interaction_ops.get_viewed(id, current_user.get_id_int())
        if not viewed:
            # 检查积分是否足够
            sufficient, message = check_points_sufficient(current_user.get_id_int(), ServiceType.UNLOCK_ROADMAP.value)
            if not sufficient:
                return jsonify({'error': message, 'points_required': True}), 402

            # 消费积分
            success, points_spent = consume_points_for_service(current_user.get_id_int(), ServiceType.UNLOCK_ROADMAP.value, translate('unlock_roadmap', lang, title=roadmap.roadmap_title))
            if not success:
                return jsonify({'error': translate('points_deduction_failed', lang), 'points_required': True}), 402

            interaction_ops.view(id, current_user.get_id_int())

        if with_mindmap:
            mindmap = get_mindmap_nosql(current_app, roadmap.mindmap_id)
        else:
            mindmap = None

        interaction_ops = RoadmapInteractionOps(db.session)

        user_participated = interaction_ops.participated(id, current_user.get_id_int())

        return jsonify({
            'user_participated': user_participated,
            'participants': roadmap.participanted,
            'completions': roadmap.completed,
            'favorites': roadmap.favorited,
            'shares': roadmap.shared,
            'title': roadmap.roadmap_title,
            'type': roadmap.roadmap_type,
            'kind': roadmap.roadmap_kind,
            'lang': roadmap.roadmap_lang,
            'mindmap': mindmap,
        })

    return jsonify({'error': translate('roadmap_not_found', lang)}), 404


@bp.route('/reset_official_roadmaps', methods=['SET'])
# @login_required
# @admin_required
def reset_official_roadmaps():
    lang = get_user_lang()
    roadmap_ops = RoadmapOps(db.session)
    roadmap_ops.reset_official_roadmaps()
    return jsonify({'message': translate('official_roadmaps_reset', lang)})


@bp.route('/submit_update', methods=['POST'])
@login_required
def submit_update():
    mindmap_id = request.form.get('mindmap_id')
    mindmap = request.form.get('mindmap')
    lang = get_user_lang()
    mindmap = json.loads(mindmap)

    old_mindmap = get_mindmap_nosql(current_app, mindmap_id)
    if old_mindmap:
        mindmap['updated_at'] = time.time()
        mindmap['updated_by'] = current_user.get_id_int()
        result =  update_mindmap_nosql(current_app, mindmap)
        current_app.logger.debug(f"update mindmap: {result} by user: {current_user.get_id_int()}")
        return jsonify({'message': translate('update_submitted', lang)})

    return jsonify({'error': translate('roadmap_not_found', lang)}), 404

@bp.route('/submit_learning_status', methods=['POST'])
@login_required
def submit_learning_status():
    """提交学习状态"""
    mindmap_id = request.form.get('mindmap_id')
    roadmap_id = request.form.get('roadmap_id')
    status = request.form.get('status')
    lang = get_user_lang()

    if not mindmap_id or not status:
        return jsonify({'error': translate('missing_required_fields', lang)}), 400

    user_id = current_user.get_id_int()

    # 确保 status 是字典对象
    if isinstance(status, str):
        try:
            status = json.loads(status)
        except json.JSONDecodeError:
            return jsonify({'error': translate('invalid_status_format', lang)}), 400

    # 使用 upsert 替代原来的 add 或 update
    mindmap_status = {
        'mindmap_id': mindmap_id,
        'status': status,  # 这里应该是一个字典，而不是字符串
        'user_id': user_id,
        'updated_at': time.time()
    }

    interaction_ops = RoadmapInteractionOps(db.session)
    interaction_ops.participant(roadmap_id, user_id)

    upsert_user_mindmap_status_nosql(current_app, user_id, mindmap_status)

    return jsonify({'message': translate('learning_status_submitted', lang)})

@bp.route('/learning_status', methods=['GET'])
@login_required
def learning_status():
    mindmap_id = request.args.get('mindmap_id')
    lang = get_user_lang()

    mindmap_status = get_learning_status_nosql(current_app, current_user.get_id_int(), mindmap_id)
    if mindmap_status:
        return jsonify(mindmap_status)
    else:
        current_app.logger.debug(f"learning status not found: {mindmap_id}")
        return jsonify({'message': translate('learning_status_not_found', lang)}), 404

@bp.route('/recent_maps', methods=['GET'])
@login_required
def recent_maps():
    offset = int(request.args.get('offset', '0'))
    limit = int(request.args.get('limit', '3'))
    user_id = current_user.get_id_int()

    interaction_ops = RoadmapInteractionOps(db.session)
    count = interaction_ops.get_participants_count_of_user(user_id)

    mindmap_statuses = get_learning_list_nosql(current_app, user_id, offset, limit)

    recent_maps = []
    for mindmap_status in mindmap_statuses:
        # 确保 status 是字典对象
        status = mindmap_status['status']
        if isinstance(status, str):
            try:
                # 尝试将字符串解析为 JSON
                status = json.loads(status)
            except json.JSONDecodeError:
                # 如果解析失败，则创建一个空字典
                current_app.logger.error(f"Failed to parse status: {status}")
                status = {}

        # 如果 status 仍然不是字典，则创建一个空字典
        if not isinstance(status, dict):
            status = {}

        total_nodes = len(status)
        completed_nodes = 0
        for node_id, node_status in status.items():
            if node_status == 'done':
                completed_nodes += 1

        recent_maps.append({
            'mindmap_id': mindmap_status['mindmap_id'],
            'updated_at': mindmap_status['updated_at'],
            'completed_nodes': completed_nodes,
            'total_nodes': total_nodes,
        })

    results = []

    recent_maps = sorted(recent_maps, key=lambda x: x['updated_at'], reverse=True)
    roadmap_ops = RoadmapOps(db.session)
    for recent_map in recent_maps:
        roadmap = roadmap_ops.get_roadmap_by_mindmap_id(recent_map['mindmap_id'])
        if roadmap:
            mindmap = get_mindmap_nosql(current_app, recent_map['mindmap_id'])
            result = roadmap.to_dict()
            result['subtitle'] = stats_of_mindmap(mindmap)
            current_app.logger.debug(f"recent_map_id: {recent_map['mindmap_id']}")
            result['description'] = mindmap['description']
            result['completed'] = recent_map['completed_nodes']
            result['total'] = recent_map['total_nodes']
            result['total_stages'] = len(mindmap.get('children', []))
            results.append(result)

    return jsonify({
        'roadmaps': results,
        'count': count,
    })

@bp.route('/heading_quote', methods=['GET'])
@login_required
def heading_quote():
    lang = get_user_lang()
    quotes = QUOTES.get(lang, QUOTES['zh_CN'])

    user_id = current_user.get_id_int()
    today = int(time.time() / 86400)
    seed = user_id + today
    random.seed(seed)
    current_app.logger.debug(f"user_id: {user_id}, today: {today}, seed: {seed}")
    quote = random.choice(quotes)

    return jsonify({'quote': quote})

# ------------------------------------------------------------
# only for admin

@bp.route('/delete_index', methods=['DELETE'])
@login_required
@admin_required
def delete_index():
    index_name = request.args.get('name')
    lang = get_user_lang()
    delete_index_nosql(current_app, index_name)
    current_app.logger.debug('index deleted')
    return jsonify({'message': translate('index_deleted', lang)})
