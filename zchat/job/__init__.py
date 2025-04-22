import json
import argparse
import sys
import os
from pathlib import Path
import tempfile
import uuid
import time

from flask import (
    Blueprint, request, jsonify, current_app, g, send_file, render_template
)
from werkzeug.utils import secure_filename

from zchat.auth import login_required, current_user
from zchat.apis.ocr import ocr_file
from zchat.nosql import (
    get_file_records_nosql,
    add_file_records_nosql,
    update_file_records_nosql,
    add_jd_record_nosql,
    get_jd_records_nosql
)

from zchat.job.jd_parser import parse_jd
from zchat.models.points import ServiceType
from zchat.points import check_points_sufficient, consume_points_for_service

bp = Blueprint('job', __name__, url_prefix='/job')

@bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    jd_file = request.files.get('jd_file', None)
    jd_file_name = request.form.get('jd_file_name', None)
    jd_text = request.form.get('jd_text', None)

    if not jd_file and not jd_text and not jd_file_name:
        return jsonify({'error': 'No JD file or JD text provided'}), 400

    user_id = current_user.get_id_int()

    # 检查积分是否足够
    sufficient, message = check_points_sufficient(user_id, ServiceType.JOB_ANALYSIS.value)
    if not sufficient:
        return jsonify({'error': message, 'points_required': True}), 402

    file_records = {}

    if jd_file:
        filename = secure_filename(jd_file.filename)
        filename = f'{uuid.uuid4()}_{filename}'
        dir_path = os.path.join(current_app.instance_path, 'jds')
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_records['jd_files'] = [
            {
                'filename': jd_file.filename,
                'path': f'/jds/{filename}',
            }
        ]
        file_path = os.path.join(dir_path, filename)
        jd_file.save(file_path)
        jd = ocr_file(file_path)
    elif jd_file_name:
        old_file_records = get_file_records_nosql(current_app, user_id)
        if old_file_records:
            for jd_file in old_file_records.get('jd_files', []):
                if jd_file['filename'] == jd_file_name:
                    file_path = jd_file['path']
                    break
        if file_path:
            full_file_path = f"{current_app.instance_path}/{file_path}"
            jd = ocr_file(full_file_path)
        else:
            jd = ''
    elif jd_text:
        jd = jd_text
    else:
        pass

    if not jd:
        return jsonify({'error': 'No JD provided'}), 400

    current_app.logger.debug(f"received jd text: {jd}")

    if len(file_records.keys()) > 0:
        file_records['id'] = user_id
        file_records['user_id'] = user_id
        old_file_records = get_file_records_nosql(current_app, user_id)
        if old_file_records:
            old_file_records['jd_files'] = old_file_records.get('jd_files', []) + file_records['jd_files']
            update_file_records_status = update_file_records_nosql(current_app, old_file_records)
            current_app.logger.debug(f"update file records status: {update_file_records_status}")
        else:
            add_file_records_status = add_file_records_nosql(current_app, file_records)
            current_app.logger.debug(f"add file records status: {add_file_records_status}")

    current_app.logger.debug(f"ready to analyze jd")

    jd_analysis_result = parse_jd(jd)
    if not jd_analysis_result:
        return jsonify({'error': 'Try again later'}), 500

    # 消费积分
    success, points_spent = consume_points_for_service(user_id, ServiceType.JOB_ANALYSIS.value, "职位分析")
    if not success:
        return jsonify({'error': '积分扣除失败，请稍后重试', 'points_required': True}), 402

    current_app.logger.debug(f"jd analysis result: {json.dumps(jd_analysis_result, indent=4, ensure_ascii=False)}")

    jd_record =  {
        'id': str(uuid.uuid4()),
        'job_title': jd_analysis_result['job_title'],
        'company': jd_analysis_result['company'],
        'jd_text': jd,
        'jd_analysis_result': jd_analysis_result,
        'file_records': file_records,
        'created_at': time.time(),
        'updated_at': time.time(),
        'points_spent': points_spent,
    }
    add_jd_record_nosql(current_app, user_id, jd_record)

    return jsonify(jd_record)

@bp.route('/analysis_history', methods=['GET'])
@login_required
def get_analysis_history():
    offset = request.args.get('offset', 0)
    limit = request.args.get('limit', 10)

    user_id = current_user.get_id_int()
    jd_records = get_jd_records_nosql(current_app, user_id, offset, limit)
    return jsonify({
        'history': jd_records,
    })
