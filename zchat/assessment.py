import time
import json
import uuid

from flask import (
    Blueprint, request, jsonify, current_app
)

from zchat.auth import login_required, current_user
from zchat.meili import *

bp = Blueprint('assessment', __name__, url_prefix='/assessment')

@bp.route('/submit_report', methods=['POST'])
def submit_report():
    report_data = json.loads(request.form.get('report_data'))
    user_id = current_user.get_id_int()
    report_id = str(uuid.uuid4())
    report_data['report_id'] = report_id
    report_data['created_at'] = time.time()

    current_app.logger.debug(f"report_data: {report_data}")
    add_user_assessment_report_to_meili(current_app, user_id, report_data)

    return jsonify({'message': 'Report submitted successfully'}), 200

@bp.route('/reports', methods=['GET'])
def get_reports():
    user_id = current_user.get_id_int()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    report_list = get_user_assessment_report_list_from_meili(current_app, user_id, offset, limit)
    return jsonify({'message': 'Report list retrieved successfully', 'reports': report_list}), 200