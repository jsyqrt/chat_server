import time
import json
from flask import Blueprint, request, jsonify, current_app, g
from flask_login import login_required, current_user

from zchat.db import db
from zchat.models.user import UserOps
from zchat.models.points import PointsOps, ServiceType
from zchat.models.subscription import SubscriptionOps, AccountType, SubscriptionType
from zchat.models.invitation import InvitationOps

bp = Blueprint('points', __name__, url_prefix='/points')

@bp.route('/balance', methods=['GET'])
@login_required
def get_balance():
    """获取用户积分余额和到期情况"""
    user_id = current_user.get_id_int()

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    # 获取用户信息
    user = user_ops.get_one(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 获取积分信息
    points_ops = PointsOps(db.session)

    # 检查并过期积分（懒更新机制）
    points_ops.check_and_expire_points()

    # 计算可用的每日积分（懒更新机制）
    daily_available = points_ops.get_daily_available_points(user_id, user.account_type)
    daily_total = points_ops.get_daily_points(user.account_type)
    daily_used = daily_total - daily_available

    # 获取明天凌晨的时间戳（积分重置时间）
    current_time = time.time()
    current_day = int(current_time / points_ops.SECONDS_PER_DAY)
    next_day_reset_time = (current_day + 1) * points_ops.SECONDS_PER_DAY  # 明天0点

    # 获取购买的积分和邀请积分
    purchased_points = points_ops.get_purchased_points(user_id)
    invitation_points = points_ops.get_invitation_points(user_id)

    # 计算总可用积分
    purchased_total = sum([p['points_amount'] for p in purchased_points])
    invitation_total = sum([p['points_amount'] for p in invitation_points])

    return jsonify({
        "account_type": user.account_type,
        "daily_total": daily_total,
        "daily_used": daily_used,
        "daily_available": daily_available,
        "daily_reset_time": next_day_reset_time,
        "purchased_total": purchased_total,
        "invitation_total": invitation_total,
        "purchased_points": purchased_points,
        "invitation_points": invitation_points,
        "total_available": daily_available + purchased_total + invitation_total
    })

@bp.route('/costs_and_rewards', methods=['GET'])
@login_required
def get_costs_and_rewards():
    """获取积分成本和奖励"""
    points_ops = PointsOps(db.session)
    return jsonify(points_ops.get_costs_and_rewards())

@bp.route('/packages', methods=['GET'])
@login_required
def get_point_packages():
    """获取积分套餐列表"""
    # 定义积分套餐
    packages = [
        {
            "id": 1,
            "name": "积分套餐A",
            "points": 1000,
            "price": 10.0,
            "validity_days": 30,
            "description": "10元购买1000积分，有效期30天"
        },
        {
            "id": 2,
            "name": "积分套餐B",
            "points": 3000,
            "price": 28.0,
            "validity_days": 30,
            "description": "28元购买3000积分，有效期30天，比单独购买更优惠"
        },
        {
            "id": 3,
            "name": "积分套餐C",
            "points": 5000,
            "price": 45.0,
            "validity_days": 30,
            "description": "45元购买5000积分，有效期30天，最实惠的选择"
        }
    ]

    return jsonify({"packages": packages})

@bp.route('/purchase', methods=['POST'])
@login_required
def purchase_points():
    """购买积分"""
    user_id = current_user.get_id_int()
    data = request.json

    package_id = data.get('package_id')
    payment_method = data.get('payment_method', 'alipay')

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    # 获取套餐信息
    packages = {
        1: {"points": 1000, "price": 10.0},
        2: {"points": 3000, "price": 28.0},
        3: {"points": 5000, "price": 45.0},
    }

    if package_id not in packages:
        return jsonify({"error": "Invalid package ID"}), 400

    package = packages[package_id]

    # TODO: 集成支付网关，处理实际支付
    # 这里简化处理，直接假设支付成功

    # 创建订单号
    order_id = f"P{int(time.time())}{user_id}"

    # 添加积分
    points_ops = PointsOps(db.session)

    # 检查并过期积分（懒更新机制）
    points_ops.check_and_expire_points()

    success = points_ops.purchase_points(
        user_id=user_id,
        points_amount=package["points"],
        payment_amount=package["price"],
        payment_order_id=order_id,
        payment_method=payment_method
    )

    if not success:
        return jsonify({"error": "Failed to purchase points"}), 500

    return jsonify({
        "order_id": order_id,
        "points": package["points"],
        "price": package["price"],
        "payment_method": payment_method,
        "status": "success",
        "message": "购买成功"
    })

@bp.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    """获取用户积分交易记录"""
    user_id = current_user.get_id_int()
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    # 获取积分信息
    points_ops = PointsOps(db.session)

    # 检查并过期积分（懒更新机制）
    points_ops.check_and_expire_points()

    transactions = points_ops.get_points_transactions(user_id, limit, offset)
    total = points_ops.get_points_transactions_count(user_id)

    return jsonify({
        "transactions": transactions,
        "total": total
    })

# 订阅相关API
@bp.route('/subscription/plans', methods=['GET'])
@login_required
def get_subscription_plans():
    """获取订阅计划列表"""
    plans = [
        {
            "id": 0,
            "type": AccountType.FREE.value,
            "name": "免费账户",
            "price": PointsOps.PRICES[AccountType.FREE.value],
            "cycle": "unlimited",
            "daily_points": PointsOps.DAILY_POINTS[AccountType.FREE.value],
            "description": f"免费账户，每天{PointsOps.DAILY_POINTS[AccountType.FREE.value]}积分"
        },
        {
            "id": 1,
            "type": SubscriptionType.BASIC.value,
            "name": "基础会员",
            "price": PointsOps.PRICES[AccountType.BASIC.value],
            "cycle": "month",
            "daily_points": PointsOps.DAILY_POINTS[AccountType.BASIC.value],
            "description": f"每月{PointsOps.PRICES[AccountType.BASIC.value]}元，每天{PointsOps.DAILY_POINTS[AccountType.BASIC.value]}积分"
        },
        {
            "id": 2,
            "type": SubscriptionType.PRO.value,
            "name": "高级会员",
            "price": PointsOps.PRICES[AccountType.PRO.value],
            "cycle": "year",
            "daily_points": PointsOps.DAILY_POINTS[AccountType.PRO.value],
            "description": f"每年{PointsOps.PRICES[AccountType.PRO.value]}元(相当于每月{PointsOps.PRICES[AccountType.PRO.value] / 12}元)，每天{PointsOps.DAILY_POINTS[AccountType.PRO.value]}积分，性价比高"
        }
    ]

    return jsonify({"plans": plans})

@bp.route('/subscription/subscribe', methods=['POST'])
@login_required
def subscribe():
    """订阅会员"""
    user_id = current_user.get_id_int()
    data = request.json

    subscription_type = data.get('subscription_type')
    payment_method = data.get('payment_method', 'alipay')

    if subscription_type not in [SubscriptionType.BASIC.value, SubscriptionType.PRO.value]:
        return jsonify({"error": "Invalid subscription type"}), 400

    # 获取订阅价格
    price = 29.9 if subscription_type == SubscriptionType.BASIC.value else 180.0

    # TODO: 集成支付网关，处理实际支付
    # 这里简化处理，直接假设支付成功

    # 创建订单号
    order_id = f"S{int(time.time())}{user_id}"

    # 创建订阅记录
    subscription_ops = SubscriptionOps(db.session)
    subscription = subscription_ops.create_subscription(
        user_id=user_id,
        subscription_type=subscription_type,
        payment_amount=price,
        payment_method=payment_method,
        payment_order_id=order_id
    )

    if not subscription:
        return jsonify({"error": "Failed to create subscription"}), 500

    # 更新用户账户类型
    user_ops = UserOps(db.session)
    account_type = AccountType.BASIC.value if subscription_type == SubscriptionType.BASIC.value else AccountType.PRO.value
    user_ops.update_account_type(
        id=user_id,
        account_type=account_type,
        subscription_start_time=subscription.start_time,
        subscription_end_time=subscription.end_time
    )

    return jsonify({
        "order_id": order_id,
        "subscription_type": subscription_type,
        "price": price,
        "payment_method": payment_method,
        "start_time": subscription.start_time,
        "end_time": subscription.end_time,
        "status": "success",
        "message": "订阅成功"
    })

@bp.route('/subscription/history', methods=['GET'])
@login_required
def subscription_history():
    """获取用户订阅历史"""
    user_id = current_user.get_id_int()
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    subscription_ops = SubscriptionOps(db.session)
    subscriptions = subscription_ops.get_subscriptions(user_id, limit, offset)

    # 获取当前活跃的订阅
    active_subscription = subscription_ops.get_active_subscription(user_id)
    active = active_subscription.to_dict() if active_subscription else None

    return jsonify({
        "subscriptions": subscriptions,
        "active": active
    })

# 邀请相关API
@bp.route('/invitation/code', methods=['GET'])
@login_required
def get_invitation_code():
    """获取用户邀请码"""
    user_id = current_user.get_id_int()

    user_ops = UserOps(db.session)
    invite_code = user_ops.get_invite_code(user_id)

    if not invite_code:
        return jsonify({"error": "Failed to get invitation code"}), 500

    # 构建邀请链接
    base_url = request.host_url.rstrip('/')
    invite_url = f"{base_url}/register?invite_code={invite_code}"

    return jsonify({
        "invite_code": invite_code,
        "invite_url": invite_url
    })

@bp.route('/invitation/records', methods=['GET'])
@login_required
def get_invitation_records():
    """获取用户邀请记录"""
    user_id = current_user.get_id_int()
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    # 检查并过期积分
    points_ops = PointsOps(db.session)
    points_ops.check_and_expire_points()

    invitation_ops = InvitationOps(db.session)

    records = invitation_ops.get_invitations_by_inviter(user_id, limit, offset)
    total = invitation_ops.get_invitations_count_by_inviter(user_id)
    total_rewards = invitation_ops.get_total_points_rewarded(user_id)

    # 补充被邀请人信息
    for record in records:
        invitee = user_ops.get_one(record['invitee_id'])
        if invitee:
            record['invitee_name'] = invitee.nickname
            record['invitee_avatar'] = invitee.avatar_name

    return jsonify({
        "total_invited": total,
        "total_rewards": total_rewards,
        "records": records
    })

# 检查是否有足够积分的辅助函数
def check_points_sufficient(user_id, service_type):
    """检查用户是否有足够的积分"""
    points_ops = PointsOps(db.session)

    # 获取服务所需积分
    required_points = points_ops.get_service_cost(service_type)

    # 获取用户信息
    user_ops = UserOps(db.session)
    user = user_ops.get_one(user_id)
    if not user:
        return False, "User not found"

    # 检查用户订阅状态（确保账户类型是最新的）
    user_ops.check_and_update_subscription_status(user_id)

    # 获取用户可用积分（这里使用懒更新机制）
    daily_available = points_ops.get_daily_available_points(user_id, user.account_type)
    purchased_points = points_ops.get_purchased_points(user_id)
    invitation_points = points_ops.get_invitation_points(user_id)

    # 计算总可用积分
    purchased_total = sum([p['points_amount'] for p in purchased_points])
    invitation_total = sum([p['points_amount'] for p in invitation_points])
    total_available = daily_available + purchased_total + invitation_total

    # 检查是否有足够积分
    if total_available < required_points:
        return False, f"积分不足，当前可用积分: {total_available}，需要积分: {required_points}"

    return True, ""

# 消费积分的辅助函数，调用之前必须先check_points_sufficient
def consume_points_for_service(user_id, service_type, description=None):
    """消费指定服务的积分"""
    points_ops = PointsOps(db.session)

    # 获取服务所需积分
    required_points = points_ops.get_service_cost(service_type)

    # 消费积分
    if not description:
        description = f"使用服务: {service_type}"

    success = points_ops.consume_points(user_id, required_points, service_type, description)

    return success, required_points

# 注册Blueprint
def init_app(app):
    app.register_blueprint(bp)