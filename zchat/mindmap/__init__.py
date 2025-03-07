import os
import json
import uuid
import time
import random

from flask import request, current_app, Blueprint, jsonify
from werkzeug.utils import secure_filename
from ocrmac import ocrmac

from zchat.auth import login_required, current_user
from zchat.db import db
from zchat.models.user import UserOps
from zchat.mindmap.from_jd import mindmap_from_jd
from zchat.mindmap.from_topic import mindmap_from_topic
from zchat.mindmap.get_description import description_from_topic_path
from zchat.meili import add_user_mindmap_to_meili, update_user_mindmap_to_meili, find_mindmaps_from_meili_for, find_user_mindmaps_from_meili_created_by

bp = Blueprint('mindmap', __name__, url_prefix='/mindmap')

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

# nodejs.json
# devops.json
# server-side-game-developer.json
# frontend.json
# computer-science.json
# python.json
# software-architect.json
# data-analyst.json
# typescript.json
# mlops.json
# vue.json
# aspnet-core.json
# postgresql-dba.json
# angular.json
# qa.json
# backend.json
# cyber-security.json
# blockchain.json
# full-stack.json
# android.json
# system-design.json
# javascript.json
# technical-writer.json
# game-developer.json
# react.json
# ux-design.json
# sql.json