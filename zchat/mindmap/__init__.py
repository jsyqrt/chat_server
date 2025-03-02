import os
import json
import uuid
import time

from flask import request, current_app, Blueprint, jsonify
from werkzeug.utils import secure_filename
from ocrmac import ocrmac

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.user import UserOps, ExpertOps, AppointmentOps
from zchat.mindmap.from_jd import mindmap_from_jd
from zchat.mindmap.from_topic import mindmap_from_topic
from zchat.mindmap.more_detail import detail_from_topic_path
from zchat.meili import add_user_mindmap_to_meili, update_user_mindmap_to_meili, find_mindmaps_from_meili_for, find_user_mindmaps_from_meili_created_by

bp = Blueprint('mindmap', __name__, url_prefix='/mindmap')

class MindmapIdGenerator:
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

    mindmap_id_generator = MindmapIdGenerator()
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

    mindmap_id_generator = MindmapIdGenerator()
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

@bp.route('/more_detail', methods=['GET'])
@login_required
def more_detail():
    topic = request.args.get('topic')
    topic_path = request.args.get('topic_path')

    detail_json = detail_from_topic_path(topic, topic_path)
    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            detail_info = json.loads(detail_json)
            is_valid = True
        except Exception as e:
            # try again
            detail_json = detail_from_topic_path(topic, topic_path)
            max_retries -= 1

    return jsonify(detail_info)
