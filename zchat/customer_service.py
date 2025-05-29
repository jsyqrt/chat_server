from flask import Blueprint, render_template, request, jsonify, current_app
import uuid
import time
from zchat.nosql import add_feedback_nosql, get_feedback_nosql, update_feedback_nosql, get_feedback_list_nosql
from zchat.auth import login_required, current_user, admin_required
from zchat.mail import send_feedback_notification_email

bp = Blueprint('customer_service', __name__, url_prefix='/customer_service')

@bp.route('/privacy_policy', methods=['GET'])
def privacy_policy():
    return render_template('customer_service/privacy_policy.html')

@bp.route('/terms_of_service', methods=['GET'])
def terms_of_service():
    return render_template('customer_service/terms_of_service.html')

@bp.route('/premium_service_agreement', methods=['GET'])
def premium_service_agreement():
    return render_template('customer_service/premium_service_agreement.html')

@bp.route('/feedback', methods=['POST'])
@login_required
def feedback():
    content = request.form['content']
    category = request.form['category']
    image_urls = request.form['image_urls']
    contact = request.form['contact']

    user_id = current_user.get_id_int()

    feedback = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'content': content,
        'category': category,
        'image_urls': image_urls,
        'contact': contact,
        'created_by': user_id,
        'created_at': time.time(),
        'status': 'pending',
    }
    add_feedback_to_nosql(current_app, feedback)

    try:
        send_feedback_notification_email(feedback)
    except Exception as e:
        current_app.logger.error(f"Failed to send feedback notification: {str(e)}")
        # We don't want to fail the feedback submission if email fails
        pass

    return jsonify({'message': '反馈成功'})

@bp.route('/feedback_list', methods=['GET'])
@login_required
@admin_required
def feedback_list():
    status = request.args.get('status', 'pending')
    offset = request.args.get('offset', 0)
    limit = request.args.get('limit', 10)
    feedback_list = get_feedback_list_nosql(current_app, status, offset, limit)
    return jsonify({'feedback_list': feedback_list})

@bp.route('/handle_feedback', methods=['POST'])
@login_required
@admin_required
def handle_feedback():
    feedback_id = request.form['feedback_id']
    status = request.form['status']
    feedback = get_feedback(current_app, feedback_id)
    feedback['status'] = status
    update_feedback(current_app, feedback)
    return jsonify({'message': '反馈处理成功'})
