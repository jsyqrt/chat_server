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
from zchat.meili import get_file_records_from_meili, \
    add_file_records_to_meili, \
    update_file_records_to_meili, \
    add_resume_optimization_record_to_meili, \
    get_resume_optimization_records_from_meili, \
    get_jd_record_from_meili

from zchat.resume.resume_optimizer import optimize as optimize_resume
from zchat.resume.resume_optimizer import compare_resumes as compare_resumes
from zchat.resume.resume_generator import generate_resume_markdown as format_resume

bp = Blueprint('resume', __name__, url_prefix='/resume')

@bp.route('/optimize', methods=['POST'])
@login_required
def optimize():
    jd_id = request.form.get('jd_id', None)
    if not jd_id:
        return jsonify({'error': 'No JD ID provided'}), 400

    resume_file = request.files.get('resume_file', None)
    resume_file_name = request.form.get('resume_file_name', None)

    if not resume_file and not resume_file_name:
        return jsonify({'error': 'No resume file or resume text provided'}), 400

    user_id = current_user.get_id_int()

    file_records = {}

    jd_record = get_jd_record_from_meili(current_app, user_id, jd_id)
    if not jd_record:
        return jsonify({'error': f'JD not found for the given JD ID: {jd_id}'}), 400

    jd = jd_record.get('jd_text', '')
    if not jd:
        return jsonify({'error': f'No JD provided for the given JD ID: {jd_id}'}), 400

    if resume_file:
        resume_file_name = resume_file.filename
        filename = secure_filename(resume_file_name)
        filename = f'{uuid.uuid4()}_{filename}'
        dir_path = os.path.join(current_app.instance_path, 'resumes')
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_records['resume_files'] = [
            {
                'filename': resume_file_name,
                'path': f'/resumes/{filename}',
            }
        ]
        file_path = os.path.join(dir_path, filename)
        resume_file.save(file_path)
        resume = ocr_file(file_path)
    elif resume_file_name:
        old_file_records = get_file_records_from_meili(current_app, user_id)
        if old_file_records:
            for resume_file in old_file_records['resume_files']:
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

    if not resume:
        return jsonify({'error': 'No resume provided'}), 400

    current_app.logger.debug(f"received jd text: {jd}, resume text: {resume}")

    if len(file_records.keys()) > 0:
        file_records['user_id'] = user_id
        old_file_records = get_file_records_from_meili(current_app, user_id)
        if old_file_records:
            old_file_records['resume_files'] = old_file_records['resume_files'] + file_records['resume_files']
            update_file_records_status = update_file_records_to_meili(current_app, old_file_records)
            current_app.logger.debug(f"update file records status: {update_file_records_status}")
        else:
            add_file_records_status = add_file_records_to_meili(current_app, file_records)
            current_app.logger.debug(f"add file records status: {add_file_records_status}")

    current_app.logger.debug(f"ready to optimize resume")

    optimized_resume = optimize_resume(jd, resume)
    if not optimized_resume:
        return jsonify({'error': 'Try again later'}), 500

    current_app.logger.debug(f"optimized resume: {json.dumps(optimized_resume, indent=4, ensure_ascii=False)}")

    comparison = compare_resumes(resume, optimized_resume, jd)
    if not comparison:
        return jsonify({'error': 'Try again later'}), 500

    current_app.logger.debug(f"comparison: {json.dumps(comparison, indent=4, ensure_ascii=False)}")

    formatted_resume = format_resume(optimized_resume["optimized_resume"], include_css=False)
    current_app.logger.debug(f"formatted resume: {formatted_resume}")

    resume_optimization_record =  {
        'id': str(uuid.uuid4()),
        'resume_file_name': resume_file_name,
        'original_resume_text': resume,
        'optimized_resume': optimized_resume,
        'comparison': comparison,
        'optimized_resume_formatted': formatted_resume,
        'jd_id': jd_id,
        'file_records': file_records,
        'created_at': time.time(),
        'updated_at': time.time(),
    }
    add_resume_optimization_record_to_meili(current_app, user_id, resume_optimization_record)
    return jsonify(resume_optimization_record)


@bp.route('/optimization_history', methods=['GET'])
@login_required
def optimization_history():
    offset = request.args.get('offset', 0)
    limit = request.args.get('limit', 10)

    user_id = current_user.get_id_int()
    resume_optimization_records = get_resume_optimization_records_from_meili(current_app, user_id, offset, limit)
    return jsonify({
        'history': resume_optimization_records,
    })
