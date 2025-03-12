from flask import Blueprint, render_template

bp = Blueprint('customer_service', __name__, url_prefix='/customer_service')

@bp.route('/privacy_policy', methods=['GET'])
def privacy_policy():
    return render_template('customer_service/privacy_policy.html')

@bp.route('/terms_of_service', methods=['GET'])
def terms_of_service():
    return render_template('customer_service/terms_of_service.html')

