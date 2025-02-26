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
from zchat.roadmap.from_jd import roadmap_from_jd
from zchat.roadmap.from_topic import roadmap_from_topic
from zchat.meili import add_user_roadmap_to_meili, update_user_roadmap_to_meili, find_roadmaps_from_meili_for, find_user_roadmaps_from_meili_created_by

bp = Blueprint('roadmap', __name__, url_prefix='/roadmap')

def update_ids_in_roadmap(roadmap_info):
    node_ids = {}
    for i, node in enumerate(roadmap_info['nodes']):
        node_ids[node['id']] = str(uuid.uuid4())
        roadmap_info['nodes'][i]['id'] = node_ids[node['id']]
    for i, edge in enumerate(roadmap_info['edges']):
        roadmap_info['edges'][i]['from'] = node_ids[edge['from']]
        roadmap_info['edges'][i]['to'] = node_ids[edge['to']]
    return roadmap_info

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

    jd_info_json, roadmap_json = roadmap_from_jd(jd, work_experience)

    current_app.logger.debug(f"got roadmap json")

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            jd_info = json.loads(jd_info_json)
            roadmap_info = json.loads(roadmap_json)
            is_valid = True
        except Exception as e:
            # try again
            jd_info_json, roadmap_json = roadmap_from_jd(jd, work_experience)
            max_retries -= 1

    roadmap_info = update_ids_in_roadmap(roadmap_info)
    roadmap = {
        "uuid": str(uuid.uuid4()),
        'roadmap_title': jd_info['job_title'],
        'roadmap_type': 'user',
        'roadmap_kind': 'job',
        'jd_info': jd_info,
        'roadmap_info': roadmap_info,
        'created_at': time.time(),
        'updated_at': time.time(),
        'created_by': current_user.get_id_int(),
    }

    add_user_roadmap_to_meili(current_app, roadmap)
    return jsonify(roadmap)

@bp.route('/from_topic', methods=['GET'])
@login_required
def from_topic():
    topic = request.args.get('topic')
    roadmap_json = roadmap_from_topic(topic)

    is_valid = False
    max_retries = 3
    while not is_valid and max_retries > 0:
        try:
            roadmap_info = json.loads(roadmap_json)
            is_valid = True
        except Exception as e:
            # try again
            roadmap_json = roadmap_from_topic(topic)
            max_retries -= 1

    roadmap_info = update_ids_in_roadmap(roadmap_info)
    roadmap = {
        "uuid": str(uuid.uuid4()),
        'roadmap_title': topic,
        'roadmap_type': 'user',
        'roadmap_kind': 'skill',
        'roadmap_info': roadmap_info,
        'created_at': time.time(),
        'updated_at': time.time(),
        'created_by': current_user.get_id_int(),
    }

    add_user_roadmap_to_meili(current_app, roadmap)
    return jsonify(roadmap)

@bp.route('/search_topic', methods=['GET'])
@login_required
def search_topic():
    topic = request.args.get('topic')
    roadmaps = find_roadmaps_from_meili_for(current_app, topic)
    return jsonify(roadmaps)

@bp.route('/my_roadmaps', methods=['GET'])
@login_required
def my_roadmaps():
    roadmaps = find_user_roadmaps_from_meili_created_by(current_app, current_user.get_id_int())
    return jsonify(roadmaps)
