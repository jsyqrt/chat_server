import os
import json
import uuid
import time
import random
from enum import Enum

from flask import request, current_app, Blueprint, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from zchat.auth import login_required, current_user, admin_required
from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.roadmap import RoadmapOps, RoadmapInteractionOps
from zchat.roadmap.from_jd import mindmap_from_jd_and_resume
from zchat.roadmap.from_topic import mindmap_from_topic
from zchat.roadmap.get_description import description_from_topic_path, description_from_topic_path_stream
from zchat.nosql import *
from zchat.apis.ocr import ocr_file
from zchat.models.points import ServiceType
from zchat.points import check_points_sufficient, consume_points_for_service

bp = Blueprint('roadmap', __name__, url_prefix='/roadmap')

class RoadmapType(Enum):
    OFFICIAL = 'official'
    USER = 'user'

class RoadmapKind(Enum):
    SKILL = 'skill'
    JOB = 'job'

class RoadmapStatus(Enum):
    CREATED = 0
    VERIFIED = 1
    PUBLIC = 2

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
        return jsonify({'error': 'No JD ID provided'}), 400

    user_id = current_user.get_id_int()

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.CREATE_ROADMAP.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    resume_file = request.files.get('resume_file', None)
    resume_file_name = request.form.get('resume_file_name', None)

    jd_record = get_jd_record_nosql(current_app, user_id, jd_id)
    if not jd_record:
        return jsonify({'error': f'JD not found for the given JD ID: {jd_id}'}), 400

    jd = jd_record.get('jd_text', '')
    if not jd:
        return jsonify({'error': f'No JD provided for the given JD ID: {jd_id}'}), 400

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
        file_records['user_id'] = user_id
        old_file_records = get_file_records_nosql(current_app, user_id)
        if old_file_records:
            old_file_records['resume_files'] = old_file_records.get('resume_files', []) + file_records['resume_files']
            add_file_records_nosql(current_app, old_file_records)

    mindmap_json = mindmap_from_jd_and_resume(jd, resume)

    current_app.logger.debug(f"got mindmap json: {mindmap_json}")

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            mindmap_info = json.loads(mindmap_json)
            is_valid = True
        except Exception as e:
            # try again
            mindmap_json = mindmap_from_jd_and_resume(jd, resume)
            max_retries -= 1

    if not mindmap_info:
        return jsonify({'error': 'Failed to create mindmap'}), 400

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
    roadmap_subtitle = '定制专属职业成长路径'
    roadmap_type = RoadmapType.USER.value
    roadmap_kind = RoadmapKind.JOB.value
    roadmap_status = RoadmapStatus.VERIFIED.value
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
        mindmap_id=mindmap_id,
        created_by=created_by,
        industry_tag=industry_tag,
        job_tag=job_tag,
        skill_tag=skill_tag,
    )

    add_mindmap_nosql(current_app, mindmap)

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.CREATE_ROADMAP.value, f"创建学习路径({roadmap.roadmap_title})")
    if not success:
        return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

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
        'mindmap': mindmap,
        'points_spent': points_spent
    })


@bp.route('/create_from_topic', methods=['POST'])
@login_required
def create_from_topic():
    topic = request.form.get('topic')
    skill_level = request.form.get('skill_level')
    learning_goal = request.form.get('learning_goal', '')
    user_background = request.form.get('user_background', '')
    other_prompts = request.form.get('other_prompts', '')
    user_id = current_user.get_id_int()

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.CREATE_ROADMAP.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            mindmap = mindmap_from_topic(topic, skill_level, learning_goal, user_background, other_prompts)
            if mindmap:
                mindmap = json.loads(mindmap)
                is_valid = True
        except Exception as e:
            # try again
            mindmap = mindmap_from_topic(topic, skill_level, learning_goal, user_background, other_prompts)
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
    roadmap_kind = RoadmapKind.SKILL.value
    roadmap_status = RoadmapStatus.VERIFIED.value
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
        mindmap_id=mindmap_id,
        created_by=created_by,
        industry_tag=industry_tag,
        job_tag=job_tag,
        skill_tag=skill_tag,
    )

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.CREATE_ROADMAP.value, f"创建学习路径({topic})")
    if not success:
        return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

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
        'mindmap': mindmap,
        'points_spent': points_spent
    })

@bp.route('/industry_tags', methods=['GET'])
# @login_required
def industry_tags():
    roadmap_ops = RoadmapOps(db.session)
    industry_tags = roadmap_ops.all_industry_tags()
    return jsonify({
        'industry_tags': industry_tags,
    })

@bp.route('/job_tags_of_industry_tags', methods=['GET'])
# @login_required
def job_tags_of_industry_tags():
    industry_tags = request.args.get('industry_tags')
    industry_tags = industry_tags.split(',')
    roadmap_ops = RoadmapOps(db.session)
    job_tags = []
    for industry_tag in industry_tags:
        job_tags.extend(roadmap_ops.job_tags_of_industry_tag(industry_tag))
    return jsonify({
        'job_tags': job_tags,
    })

@bp.route('/skill_tags_of_job_tags', methods=['GET'])
# @login_required
def skill_tags_of_job_tags():
    job_tags = request.args.get('job_tags')
    job_tags = job_tags.split(',')
    roadmap_ops = RoadmapOps(db.session)
    skill_tags = []
    for job_tag in job_tags:
        skill_tags.extend(roadmap_ops.skill_tags_of_job_tag(job_tag))
    return jsonify({
        'skill_tags': skill_tags,
    })

@bp.route('/search_topic', methods=['POST'])
@login_required
def search_topic():
    topics = request.form.get('topics')
    topics = topics.split(',')
    allow_user_created = request.form.get('allow_user_created', 'false') == 'true'
    limit = int(request.form.get('limit', '5'))

    current_app.logger.debug(f"search_topic: {topics}, allow_user_created: {allow_user_created}, limit: {limit}")

    roadmap_ops = RoadmapOps(db.session)
    result_ids = set()
    results = {}
    enough = False
    for topic in topics:
        roadmaps = roadmap_ops.search_roadmaps_for_topic(topic, RoadmapType.OFFICIAL.value, limit)
        current_app.logger.debug(f"search_topic roadmaps official, count: {len(roadmaps)}")
        if allow_user_created:
            roadmaps.extend(roadmap_ops.search_roadmaps_for_topic(topic, RoadmapType.USER.value, limit))
        current_app.logger.debug(f"search_topic roadmaps user, count: {len(roadmaps)}")
        for roadmap in roadmaps:
            if roadmap['id'] not in result_ids:
                if len(results) < limit:
                    result_ids.add(roadmap['id'])
                    results[roadmap['id']] = roadmap
                    mindmap = get_mindmap_nosql(current_app, roadmap['mindmap_id'])
                    roadmap['description'] = mindmap['description']
                    roadmap['subtitle'] = stats_of_mindmap(mindmap)
                    roadmap['total_stages'] = len(mindmap.get('children', []))
                else:
                    enough = True
                    break
        if enough:
            break

    current_app.logger.debug(f"search_topic results count: {len(results)}")

    return jsonify(list(results.values()))

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

@bp.route('/description', methods=['POST'])
@login_required
def description():
    topic = request.form.get('topic')
    topic_path = request.form.get('topic_path')
    topic_path = topic_path.split(',')
    user_id = current_user.get_id_int()

    current_app.logger.debug(f"description topic: {topic}, topic_path: {topic_path}")

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.GET_DESCRIPTION.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    description_json = description_from_topic_path(topic, topic_path)
    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            description_info = json.loads(description_json)
            is_valid = True
        except Exception as e:
            # try again
            description_json = description_from_topic_path(topic, topic_path)
            max_retries -= 1

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.GET_DESCRIPTION.value, f"获取知识详情({topic})")
    if not success:
        return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

    return jsonify({
        'description': description_info,
        'points_spent': points_spent
    })

@bp.route('/description_stream', methods=['POST'])
@login_required
def description_stream():
    topic = request.form.get('topic')
    topic_path = request.form.get('topic_path')
    topic_path = topic_path.split(',')
    user_id = current_user.get_id_int()

    current_app.logger.debug(f"description_stream topic: {topic}, topic_path: {topic_path}")

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.GET_DESCRIPTION.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.GET_DESCRIPTION.value, f"获取知识详情({topic})")
    if not success:
        return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

    def generate():
        for chunk in description_from_topic_path_stream(topic, topic_path):
            yield chunk

    return Response(stream_with_context(generate()), mimetype='text/plain')

# ------------------------------------------------------------

def stats_of_mindmap(mindmap):
    num_stages = len(mindmap.get('children', []))

    num_skills = 0
    for stage in mindmap.get('children', []):
        num_skills += len(stage.get('children', []))

    num_resources = 0
    for stage in mindmap.get('children', []):
        for skill in stage.get('children', []):
            num_resources += len(skill.get('links', []))

    resources_str = ''
    if num_resources > 10:
        resources_str = f'· {num_resources//10*10}+资源'
    elif num_resources > 0:
        resources_str = f'· {num_resources}个资源'
    else:
        resources_str = ''

    return f'{num_stages}个阶段 · {num_skills}个核心技能' + resources_str

@bp.route('/official_maps', methods=['GET'])
@login_required
def official_maps():
    roadmap_ops = RoadmapOps(db.session)
    official_roadmaps = roadmap_ops.get_official_roadmaps()
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
            success, points_spent = consume_points_for_service(current_user.get_id_int(), ServiceType.UNLOCK_ROADMAP.value, f"解锁学习路径({roadmap.roadmap_title})")
            if not success:
                return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

            interaction_ops.view(id, current_user.get_id_int())

        if with_mindmap:
            mindmap = get_mindmap_nosql(current_app, roadmap.mindmap_id)
        else:
            mindmap = None

        interaction_ops = RoadmapInteractionOps(db.session)
        interaction_stats = interaction_ops.get_stats(id)

        user_participated = interaction_ops.participated(id, current_user.get_id_int())

        return jsonify({
            'user_participated': user_participated,
            'participants': interaction_stats['participants'],
            'completions': interaction_stats['completions'],
            'favorites': interaction_stats['favorites'],
            'shares': interaction_stats['shares'],
            'title': roadmap.roadmap_title,
            'type': roadmap.roadmap_type,
            'kind': roadmap.roadmap_kind,
            'mindmap': mindmap,
        })

    return jsonify({'error': 'Roadmap not found'}), 404


@bp.route('/reset_official_roadmaps', methods=['SET'])
# @login_required
# @admin_required
def reset_official_roadmaps():
    roadmap_ops = RoadmapOps(db.session)
    roadmap_ops.reset_official_roadmaps()
    return jsonify({'message': 'Official roadmaps reset'})


@bp.route('/submit_update', methods=['POST'])
@login_required
def submit_update():
    mindmap_id = request.form.get('mindmap_id')
    mindmap = request.form.get('mindmap')
    mindmap = json.loads(mindmap)

    old_mindmap = get_mindmap_nosql(current_app, mindmap_id)
    if old_mindmap:
        mindmap['updated_at'] = time.time()
        mindmap['updated_by'] = current_user.get_id_int()
        result =  update_mindmap_nosql(current_app, mindmap)
        current_app.logger.debug(f"update mindmap: {result} by user: {current_user.get_id_int()}")
        return jsonify({'message': 'Update submitted'})

    return jsonify({'error': 'Roadmap not found'}), 404

@bp.route('/submit_learning_status', methods=['POST'])
@login_required
def submit_learning_status():
    """提交学习状态"""
    mindmap_id = request.form.get('mindmap_id')
    roadmap_id = request.form.get('roadmap_id')
    status = request.form.get('status')

    if not mindmap_id or not status:
        return jsonify({'error': 'Missing required fields'}), 400

    user_id = current_user.get_id_int()

    # 确保 status 是字典对象
    if isinstance(status, str):
        try:
            status = json.loads(status)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid status format'}), 400

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

    return jsonify({'message': 'Learning status submitted successfully'})

@bp.route('/learning_status', methods=['GET'])
@login_required
def learning_status():
    mindmap_id = request.args.get('mindmap_id')

    mindmap_status = get_learning_status_nosql(current_app, current_user.get_id_int(), mindmap_id)
    if mindmap_status:
        return jsonify(mindmap_status)
    else:
        current_app.logger.debug(f"learning status not found: {mindmap_id}")
        return jsonify({'message': 'Learning status not found'}), 404

@bp.route('/recent_maps', methods=['GET'])
@login_required
def recent_maps():
    offset = int(request.args.get('offset', '0'))
    limit = int(request.args.get('limit', '3'))
    user_id = current_user.get_id_int()

    interaction_ops = RoadmapInteractionOps(db.session)
    count = interaction_ops.get_participants_count_of_user(user_id)

    mindmap_statuses = get_learning_list_nosql(current_app, user_id, offset, limit)

    current_app.logger.debug(f'mindmap_statuses: {mindmap_statuses}')

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
            current_app.logger.debug(f"mindmap: {mindmap}, recent_map_id: {recent_map['mindmap_id']}")
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
    quotes = [
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
    ]
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
    delete_index_nosql(current_app, index_name)
    current_app.logger.debug('index deleted')
    return jsonify({'message': 'Index deleted'})
