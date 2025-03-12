import os
import json
import uuid
import time
import random

from flask import request, current_app, Blueprint, jsonify
from werkzeug.utils import secure_filename
from ocrmac import ocrmac

from zchat.auth import login_required, current_user, admin_required
from zchat.db import db
from zchat.models.user import UserOps
from zchat.models.roadmap import RoadmapOps, RoadmapInteractionOps
from zchat.roadmap.from_jd import mindmap_from_jd
from zchat.roadmap.from_topic import mindmap_from_topic
from zchat.roadmap.get_description import description_from_topic_path
from zchat.meili import \
    add_user_mindmap_to_meili, \
    update_user_mindmap_to_meili, \
    find_mindmaps_from_meili_for, \
    find_user_mindmaps_from_meili_created_by, \
    add_user_mindmap_status_to_meili, \
    update_user_mindmap_status_to_meili, \
    get_learning_status_from_meili, \
    get_learning_list_from_meili, \
    delete_index_from_meili

bp = Blueprint('roadmap', __name__, url_prefix='/roadmap')

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
        updated_map['description'] = map.get('title')
        updated_map['done'] = random.random() > 0.7

        children = map.get('children', [])
        if children:
            new_children = []
            for item in children:
                if isinstance(item, dict):
                    new_children.append(self.generate_for_map(item))
            updated_map['children'] = new_children

        return updated_map


@bp.route('/from_jd_image', methods=['POST'])
@login_required
def from_jd_image():
    image_file = request.files.get('image')
    if not image_file:
        return jsonify({'error': 'No image file provided'}), 400

    current_app.logger.debug("received jd image")

    filename = secure_filename(image_file.filename)
    file_path = os.path.join(current_app.static_folder, 'images', filename)
    image_file.save(file_path)

    current_app.logger.debug(f"saved jd image to {file_path}")

    work_experience = request.form.get('work_experience', '1-3年')

    # 处理图片文件
    annotations = ocrmac.OCR(file_path, language_preference=['zh-Hans']).recognize()
    jd = '\n'.join([a[0] for a in annotations])

    current_app.logger.debug(f"ocr result: {jd}")

    jd_info_json, mindmap_json = mindmap_from_jd(jd, work_experience)

    current_app.logger.debug(f"got mindmap json")

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            jd_info = json.loads(jd_info_json)
            mindmap_info = json.loads(mindmap_json)
            is_valid = True
        except Exception as e:
            # try again
            jd_info_json, mindmap_json = mindmap_from_jd(jd, work_experience)
            max_retries -= 1

    mindmap_id_generator = MindmapModifier()
    mindmap_info = mindmap_id_generator.generate(mindmap_info)
    mindmap = {
        "uuid": str(uuid.uuid4()),
        'mindmap_title': jd_info['job_title'],
        'mindmap_type': 'user',
        'mindmap_kind': 'job',
        'jd_info': jd_info,
        'mindmap_info': mindmap_info,
        'created_at': time.time(),
        'updated_at': time.time(),
        'created_by': current_user.get_id_int(),
    }

    add_user_mindmap_to_meili(current_app, mindmap)
    return jsonify(mindmap)

@bp.route('/from_topic', methods=['GET'])
@login_required
def from_topic():
    topic = request.args.get('topic')
    mindmap_json = mindmap_from_topic(topic)

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            mindmap_info = json.loads(mindmap_json)
            is_valid = True
        except Exception as e:
            # try again
            mindmap_json = mindmap_from_topic(topic)
            max_retries -= 1

    mindmap_id_generator = MindmapModifier()
    mindmap_info = mindmap_id_generator.generate(mindmap_info)
    mindmap = {
        "uuid": str(uuid.uuid4()),
        'mindmap_title': topic,
        'mindmap_type': 'user',
        'mindmap_kind': 'skill',
        'mindmap_info': mindmap_info,
        'created_at': time.time(),
        'updated_at': time.time(),
        'created_by': current_user.get_id_int(),
    }

    add_user_mindmap_to_meili(current_app, mindmap)
    return jsonify(mindmap)

@bp.route('/search_topic', methods=['GET'])
@login_required
def search_topic():
    topic = request.args.get('topic')
    mindmaps = find_mindmaps_from_meili_for(current_app, topic)
    return jsonify(mindmaps)

@bp.route('/my_mindmaps', methods=['GET'])
@login_required
def my_mindmaps():
    mindmaps = find_user_mindmaps_from_meili_created_by(current_app, current_user.get_id_int())
    return jsonify(mindmaps)

@bp.route('/description', methods=['GET'])
@login_required
def description():
    topic = request.args.get('topic')
    topic_path = request.args.get('topic_path')

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

    return jsonify(description_info)

@bp.route('/demo_map', methods=['GET'])
# @login_required
def demo_map():
    # name = 'backend-engineer.json'
    name = 'mybackend.json'
    with open(os.path.join(current_app.instance_path, name), 'r') as f:
        mindmap = json.load(f)
    # mindmap_id_generator = MindmapModifier()
    # mindmap = mindmap_id_generator.generate(mindmap)
    return jsonify({
        'participants': 1258,
        'completions': 342,
        'favorites': 567,
        'mindmap_title': '后端工程师学习路径',
        'mindmap_type': 'official',
        'mindmap_kind': 'role',
        'mindmap_info': mindmap,
    })

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
        with open(os.path.join(current_app.instance_path, item['id']), 'r') as f:
            mindmap = json.load(f)

        item['description'] = stats_of_mindmap(mindmap)

    return jsonify(official_roadmaps)

@bp.route('/map', methods=['GET'])
@login_required
def get_map():
    id = request.args.get('id')
    roadmap_ops = RoadmapOps(db.session)
    roadmap = roadmap_ops.get_roadmap(id)
    if roadmap:
        if roadmap.roadmap_type == 'official':
            with open(os.path.join(current_app.instance_path, id), 'r') as f:
                mindmap = json.load(f)

            interaction_ops = RoadmapInteractionOps(db.session)
            interaction_stats = interaction_ops.get_stats(id)

            return jsonify({
                'participants': interaction_stats['participants'],
                'completions': interaction_stats['completions'],
                'favorites': interaction_stats['favorites'],
                'shares': interaction_stats['shares'],
                'title': roadmap.roadmap_title,
                'type': roadmap.roadmap_type,
                'kind': roadmap.roadmap_kind,
                'mindmap': mindmap,
            })

        # TODO other roadmap types

    return jsonify({'error': 'Roadmap not found'}), 404


@bp.route('/reset_official_roadmaps', methods=['SET'])
@login_required
@admin_required
def reset_official_roadmaps():
    roadmap_ops = RoadmapOps(db.session)
    roadmap_ops.reset_official_roadmaps()
    return jsonify({'message': 'Official roadmaps reset'})


@bp.route('/submit_learning_status', methods=['POST'])
@login_required
def submit_learning_status():
    mindmap_id = request.form.get('mindmap_id')
    status = request.form.get('status')
    status = json.loads(status)

    mindmap_status = {
        'mindmap_id': mindmap_id,
        'status': status,
        'created_at': time.time(),
        'updated_at': time.time(),
        'created_by': current_user.get_id_int(),
    }

    add_user_mindmap_status_to_meili(current_app, current_user.get_id_int(), mindmap_status)
    current_app.logger.debug(f"submit learning status: {mindmap_id}, {status}")
    return jsonify({'message': 'Learning status submitted'})

@bp.route('/learning_status', methods=['GET'])
@login_required
def learning_status():
    mindmap_id = request.args.get('mindmap_id')

    mindmap_status = get_learning_status_from_meili(current_app, current_user.get_id_int(), mindmap_id)
    if mindmap_status:
        mindmap_status = mindmap_status['hits'][0]
        current_app.logger.debug(f"learning status: {mindmap_status}")
        return jsonify(mindmap_status)
    else:
        current_app.logger.debug(f"learning status not found: {mindmap_id}")
        return jsonify({'message': 'Learning status not found'})


@bp.route('/recent_maps', methods=['GET'])
@login_required
def recent_maps():
    offset = int(request.args.get('offset', '0'))
    limit = int(request.args.get('limit', '3'))

    user_id = current_user.get_id_int()
    mindmap_statuses = get_learning_list_from_meili(current_app, user_id, offset, limit)

    recent_maps = []
    for mindmap_status in mindmap_statuses:
        total_nodes = len(mindmap_status['status'])
        completed_nodes = 0
        for node in mindmap_status['status'].items():
            if node[1] == 'done':
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
            if roadmap.roadmap_type == 'official':
                with open(os.path.join(current_app.instance_path, roadmap.roadmap_id), 'r') as f:
                    mindmap = json.load(f)
                result = roadmap.to_dict()
                result['description'] = stats_of_mindmap(mindmap)
                result['progress'] = recent_map['completed_nodes'] / recent_map['total_nodes']
                result['progressText'] = f'{recent_map["completed_nodes"]/recent_map["total_nodes"]*100:.2f}%'
                result['stageText'] = f'{recent_map["completed_nodes"]}/{recent_map["total_nodes"]}已掌握'
                results.append(result)

            # TODO other roadmap types


    return jsonify(results)

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
    delete_index_from_meili(current_app, 'user_mindmap_status_1')
    current_app.logger.debug('index deleted')
    return jsonify({'message': 'Index deleted'})
