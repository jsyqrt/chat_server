import time
import json
from flask import Blueprint, request, jsonify, current_app, g
from flask_login import login_required, current_user

from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.points import PointsOps, ServiceType
from zchat.models.subscription import SubscriptionOps, AccountType, SubscriptionType
from zchat.models.invitation import InvitationOps
from zchat.models.payment import PaymentOrderOps, OrderType, PaymentMethod, OrderStatus
from zchat.utils.alipay_utils import AlipayService

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
    """积分购买下单接口 - 创建订单，生成支付宝支付字符串"""
    user_id = current_user.get_id_int()
    data = request.json

    current_app.logger.debug(f"Points purchase initiated by user {user_id} with data: {data}")

    package_id = data.get('package_id')
    payment_method = data.get('payment_method', PaymentMethod.ALIPAY.value)

    # 检查用户订阅状态
    user_ops = UserOps(db.session)
    user_ops.check_and_update_subscription_status(user_id)

    # 获取套餐信息
    packages = {
        1: {"points": 1000, "price": 10.0, "name": "积分套餐A"},
        2: {"points": 3000, "price": 28.0, "name": "积分套餐B"},
        3: {"points": 5000, "price": 45.0, "name": "积分套餐C"},
    }

    if package_id not in packages:
        return jsonify({"error": "Invalid package ID"}), 400

    package = packages[package_id]

    # 创建支付订单
    payment_ops = PaymentOrderOps(db.session)
    current_app.logger.debug(f"Creating payment order for user {user_id}, package {package_id}, payment method {payment_method}")
    order = payment_ops.create_order(
        user_id=user_id,
        order_type=OrderType.POINTS_PURCHASE.value,
        item_id=package_id,
        amount=package["price"],
        payment_method=payment_method,
        extra_data={"points": package["points"]}
    )

    if not order:
        current_app.logger.error(f"Failed to create payment order for user {user_id}, package {package_id}")
        return jsonify({"error": "Failed to create order"}), 500

    current_app.logger.debug(f"Order created successfully: {order.order_id}")

    # 生成支付字符串
    if payment_method == PaymentMethod.ALIPAY.value:
        current_app.logger.debug(f"Generating Alipay order string for order {order.order_id}")
        order_string = AlipayService.generate_order_string(
            subject=package["name"],
            out_trade_no=order.order_id,
            total_amount=package["price"],
            body=f"购买{package['points']}积分"
        )

        if not order_string:
            current_app.logger.error(f"Failed to generate Alipay payment string for order {order.order_id}")
            return jsonify({"error": "Failed to generate payment string"}), 500

        current_app.logger.debug(f"Alipay order string generated successfully for order {order.order_id}")
    else:
        # 其他支付方式，目前不支持
        return jsonify({"error": "Unsupported payment method"}), 400

    current_app.logger.debug(f"Returning payment information to client for order {order.order_id}")
    return jsonify({
        "order_id": order.order_id,
        "points": package["points"],
        "price": package["price"],
        "payment_method": payment_method,
        "status": OrderStatus.PENDING.value,
        "message": order_string  # 支付宝支付字符串
    })

@bp.route('/purchase/verify', methods=['GET'])
@login_required
def verify_points_purchase():
    """验证积分购买支付状态"""
    user_id = current_user.get_id_int()
    order_id = request.args.get('order_id')

    current_app.logger.debug(f"Points purchase verification requested by user {user_id} for order {order_id}")

    if not order_id:
        current_app.logger.warning(f"Order ID missing in verification request from user {user_id}")
        return jsonify({"error": "Order ID is required"}), 400

    # 获取订单信息
    payment_ops = PaymentOrderOps(db.session)
    order = payment_ops.get_order_by_id(order_id)

    if not order:
        current_app.logger.warning(f"Order {order_id} not found during verification for user {user_id}")
        return jsonify({"error": "Order not found"}), 404

    current_app.logger.debug(f"Retrieved order {order_id} - status: {order.status}, payment method: {order.payment_method}")

    # 检查订单所有者
    if order.user_id != user_id:
        return jsonify({"error": "Permission denied"}), 403

    # 检查订单类型
    if order.order_type != OrderType.POINTS_PURCHASE.value:
        return jsonify({"error": "Invalid order type"}), 400

    # 解析附加数据
    extra_data = json.loads(order.extra_data) if order.extra_data else {}
    points = extra_data.get('points', 0)
    current_app.logger.debug(f"Order {order_id} extra data: {extra_data}")

    # 如果订单状态为待支付，则查询支付宝订单状态
    if order.status == OrderStatus.PENDING.value and order.payment_method == PaymentMethod.ALIPAY.value:
        current_app.logger.debug(f"Querying Alipay for payment status of order {order_id}")
        # 调用支付宝查询接口
        payment_result = AlipayService.verify_payment(order.order_id)

        current_app.logger.debug(f"Alipay payment verification result for order {order_id}: {payment_result}")

        if payment_result and payment_result['success']:
            # 支付成功
            trade_status = payment_result.get('trade_status', '')
            current_app.logger.debug(f"Alipay trade status for order {order_id}: {trade_status}")

            if AlipayService.is_payment_successful(trade_status):
                current_app.logger.debug(f"Payment successful for order {order_id}, updating order status")
                # 更新订单状态
                payment_ops.update_order_status(
                    order_id=order.order_id,
                    status=OrderStatus.PAID.value,
                    transaction_id=payment_result['trade_no']
                )

                # 为用户添加积分
                current_app.logger.debug(f"Adding {points} points to user {user_id} for order {order_id}")
                points_ops = PointsOps(db.session)
                success = points_ops.purchase_points(
                    user_id=user_id,
                    points_amount=points,
                    payment_amount=order.amount,
                    payment_order_id=order.order_id,
                    payment_method=order.payment_method
                )

                if success:
                    current_app.logger.debug(f"Successfully added points for order {order_id}")
                else:
                    current_app.logger.error(f"Failed to add points for order {order_id}")

                return jsonify({
                    "success": True,
                    "order_id": order.order_id,
                    "status": OrderStatus.PAID.value,
                    "message": "支付成功",
                    "points": points,
                    "transaction_id": payment_result['trade_no']
                })
            else:
                current_app.logger.debug(f"Payment not yet successful for order {order_id}, status: {trade_status}")
                # 支付未成功
                return jsonify({
                    "success": False,
                    "order_id": order.order_id,
                    "status": order.status,
                    "message": "支付处理中",
                    "points": points,
                })

    # 返回订单当前状态
    current_app.logger.debug(f"Returning current order status for order {order_id}: {order.status}")
    return jsonify({
        "success": order.status == OrderStatus.PAID.value,
        "order_id": order.order_id,
        "status": order.status,
        "message": "支付成功" if order.status == OrderStatus.PAID.value else (
            "支付失败" if order.status == OrderStatus.FAILED.value else
            "已取消" if order.status == OrderStatus.CANCELLED.value else "待支付"
        ),
        "points": points,
        "transaction_id": order.transaction_id
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

# 获取用户支付订单
@bp.route('/orders', methods=['GET'])
@login_required
def get_user_orders():
    """获取用户支付订单列表"""
    user_id = current_user.get_id_int()
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 10))
    order_type = request.args.get('order_type')
    status = request.args.get('status')

    payment_ops = PaymentOrderOps(db.session)
    orders = payment_ops.get_user_orders(
        user_id=user_id,
        order_type=order_type,
        status=status,
        limit=limit,
        offset=offset
    )

    total = payment_ops.count_user_orders(
        user_id=user_id,
        order_type=order_type,
        status=status
    )

    return jsonify({
        "orders": orders,
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
    """订阅会员下单接口 - 创建订单，生成支付宝支付字符串"""
    user_id = current_user.get_id_int()
    data = request.json

    current_app.logger.debug(f"Subscription initiated by user {user_id} with data: {data}")

    subscription_type = data.get('subscription_type')
    payment_method = data.get('payment_method', PaymentMethod.ALIPAY.value)

    if subscription_type not in [SubscriptionType.BASIC.value, SubscriptionType.PRO.value]:
        return jsonify({"error": "Invalid subscription type"}), 400

    # 获取订阅价格和信息
    subscription_info = {
        SubscriptionType.BASIC.value: {
            "price": PointsOps.PRICES[AccountType.BASIC.value],
            "name": "基础会员(月)",
            "daily_points": PointsOps.DAILY_POINTS[AccountType.BASIC.value]
        },
        SubscriptionType.PRO.value: {
            "price": PointsOps.PRICES[AccountType.PRO.value],
            "name": "高级会员(年)",
            "daily_points": PointsOps.DAILY_POINTS[AccountType.PRO.value]
        }
    }

    plan = subscription_info[subscription_type]

    # 创建支付订单
    current_app.logger.debug(f"Creating subscription payment order for user {user_id}, type {subscription_type}")
    item_id = 1 if subscription_type == SubscriptionType.BASIC.value else 2
    payment_ops = PaymentOrderOps(db.session)
    order = payment_ops.create_order(
        user_id=user_id,
        order_type=OrderType.SUBSCRIPTION.value,
        item_id=item_id,
        amount=plan["price"],
        payment_method=payment_method,
        extra_data={"subscription_type": subscription_type}
    )

    if not order:
        current_app.logger.error(f"Failed to create subscription order for user {user_id}, type {subscription_type}")
        return jsonify({"error": "Failed to create order"}), 500

    current_app.logger.debug(f"Subscription order created: {order.order_id}")

    # 生成支付字符串
    if payment_method == PaymentMethod.ALIPAY.value:
        order_string = AlipayService.generate_order_string(
            subject=plan["name"],
            out_trade_no=order.order_id,
            total_amount=plan["price"],
            body=f"订阅{plan['name']}，每日{plan['daily_points']}积分"
        )

        if not order_string:
            return jsonify({"error": "Failed to generate payment string"}), 500
    else:
        # 其他支付方式，目前不支持
        return jsonify({"error": "Unsupported payment method"}), 400

    # 计算可能的订阅时间（仅用于显示，实际时间在支付成功后计算）
    start_time = time.time()
    if subscription_type == SubscriptionType.BASIC.value:
        end_time = start_time + 30 * 24 * 60 * 60  # 30天
    else:
        end_time = start_time + 365 * 24 * 60 * 60  # 365天

    return jsonify({
        "order_id": order.order_id,
        "subscription_type": subscription_type,
        "price": plan["price"],
        "payment_method": payment_method,
        "start_time": start_time,
        "end_time": end_time,
        "status": OrderStatus.PENDING.value,
        "message": order_string  # 支付宝支付字符串
    })

@bp.route('/subscription/verify', methods=['GET'])
@login_required
def verify_subscription():
    """验证会员订阅支付状态"""
    user_id = current_user.get_id_int()
    order_id = request.args.get('order_id')

    if not order_id:
        return jsonify({"error": "Order ID is required"}), 400

    # 获取订单信息
    payment_ops = PaymentOrderOps(db.session)
    order = payment_ops.get_order_by_id(order_id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    # 检查订单所有者
    if order.user_id != user_id:
        return jsonify({"error": "Permission denied"}), 403

    # 检查订单类型
    if order.order_type != OrderType.SUBSCRIPTION.value:
        return jsonify({"error": "Invalid order type"}), 400

    # 解析附加数据
    extra_data = json.loads(order.extra_data) if order.extra_data else {}
    subscription_type = extra_data.get('subscription_type')

    # 获取用户当前订阅信息
    subscription_ops = SubscriptionOps(db.session)
    active_subscription = subscription_ops.get_active_subscription(user_id)

    # 获取订阅开始和结束时间
    start_time = None
    end_time = None
    if active_subscription:
        start_time = active_subscription.start_time
        end_time = active_subscription.end_time

    # 如果订单状态为待支付，则查询支付宝订单状态
    if order.status == OrderStatus.PENDING.value and order.payment_method == PaymentMethod.ALIPAY.value:
        # 调用支付宝查询接口
        payment_result = AlipayService.verify_payment(order.order_id)

        if payment_result and payment_result['success']:
            # 支付成功
            if AlipayService.is_payment_successful(payment_result['trade_status']):
                # 更新订单状态
                payment_ops.update_order_status(
                    order_id=order.order_id,
                    status=OrderStatus.PAID.value,
                    transaction_id=payment_result['trade_no']
                )

                # 创建订阅记录
                subscription = subscription_ops.create_subscription(
                    user_id=user_id,
                    subscription_type=subscription_type,
                    payment_amount=order.amount,
                    payment_method=order.payment_method,
                    payment_order_id=order.order_id
                )

                if subscription:
                    # 更新用户账户类型
                    user_ops = UserOps(db.session)
                    account_type = AccountType.BASIC.value if subscription_type == SubscriptionType.BASIC.value else AccountType.PRO.value
                    user_ops.update_account_type(
                        id=user_id,
                        account_type=account_type,
                        subscription_start_time=subscription.start_time,
                        subscription_end_time=subscription.end_time
                    )

                    # 更新开始和结束时间
                    start_time = subscription.start_time
                    end_time = subscription.end_time

                return jsonify({
                    "success": True,
                    "order_id": order.order_id,
                    "status": OrderStatus.PAID.value,
                    "message": "支付成功",
                    "subscription_type": subscription_type,
                    "start_time": start_time,
                    "end_time": end_time,
                    "transaction_id": payment_result['trade_no']
                })
            else:
                # 支付未成功
                return jsonify({
                    "success": False,
                    "order_id": order.order_id,
                    "status": order.status,
                    "message": "支付处理中",
                    "subscription_type": subscription_type,
                    "start_time": start_time,
                    "end_time": end_time
                })

    # 返回订单当前状态
    return jsonify({
        "success": order.status == OrderStatus.PAID.value,
        "order_id": order.order_id,
        "status": order.status,
        "message": "支付成功" if order.status == OrderStatus.PAID.value else (
            "支付失败" if order.status == OrderStatus.FAILED.value else
            "已取消" if order.status == OrderStatus.CANCELLED.value else "待支付"
        ),
        "subscription_type": subscription_type,
        "start_time": start_time,
        "end_time": end_time,
        "transaction_id": order.transaction_id
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