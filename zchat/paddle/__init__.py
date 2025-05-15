import json
import time
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.payment import PaymentOrderOps, OrderStatus, OrderType
from zchat.models.points import PointsOps
from zchat.models.subscription import SubscriptionOps, SubscriptionType
from zchat.utils.paddle_utils import PaddleService

# 创建蓝图
bp = Blueprint('paddle', __name__, url_prefix='/api/webhooks')

@bp.route('/paddle', methods=['POST', 'GET'])
def paddle_webhook():
    """处理Paddle事件回调"""
    try:
        # 解析通知数据
        data, signature = PaddleService.parse_webhook_data(request)
        current_app.logger.debug(f"Received Paddle webhook: {json.dumps(data, indent=4, ensure_ascii=False)}")

        # 使用SDK验证通知的真实性
        verify_result = PaddleService.verify_webhook_with_sdk(request)
        current_app.logger.debug(f"Webhook verification result: {verify_result}")

        if not verify_result:
            current_app.logger.warning("Paddle webhook verification failed")
            return "false", 400

        # 获取事件类型和事件数据
        event_type = data.get('event_type', '')
        event_data = data.get('data', {})

        current_app.logger.debug(f"Processing Paddle event: {event_type}")

        # 从事件数据中获取信息
        checkout_id = event_data.get('id', '')
        subscription_id = event_data.get('subscription_id', '')

        # 从自定义数据中获取订单ID
        custom_data = event_data.get('custom_data') or {}
        order_id = custom_data.get('order_id', '')

        # 获取支付ID
        payment_id = None
        if 'payments' in event_data:
            payments = event_data.get('payments', [])
            if payments and isinstance(payments, list) and len(payments) > 0:
                payment_id = payments[0].get('id', '')

        current_app.logger.debug(f"Event details: checkout_id={checkout_id}, subscription_id={subscription_id}, order_id={order_id}")

        # 尝试获取订单信息
        if not order_id:
            current_app.logger.warning(f"No order ID in custom_data for Paddle event: {event_type}")
            return "true"  # 返回成功，防止Paddle重试

        # 获取订单对象
        payment_ops = PaymentOrderOps(db.session)
        order = payment_ops.get_order_by_id(order_id)

        if not order:
            current_app.logger.warning(f"Order not found: {order_id}")
            return "true", 404  # 返回成功，防止Paddle重试

        # 根据事件类型处理
        if event_type == 'transaction.completed':
            # 支付成功事件
            current_app.logger.debug(f"Payment succeeded for order {order_id}")

            # 更新订单状态和Paddle信息
            order.status = OrderStatus.PAID.value
            order.payment_time = time.time()
            order.paddle_checkout_id = checkout_id
            order.paddle_payment_id = payment_id
            order.transaction_id = payment_id  # 设置交易ID
            db.session.commit()

            # 处理订单
            process_successful_payment(order)

        elif event_type == 'subscription.created':
            # 订阅创建事件
            current_app.logger.debug(f"Subscription created for order {order_id}, subscription id: {subscription_id}")

            # 更新订单状态和Paddle信息
            order.paddle_subscription_id = subscription_id
            if order.status != OrderStatus.PAID.value:
                order.status = OrderStatus.PAID.value
                order.payment_time = time.time()
            db.session.commit()

        elif event_type == 'subscription.canceled':
            # 订阅取消
            current_app.logger.debug(f"Subscription cancelled for order {order_id}")

            # 获取用户订阅信息
            user_id = order.user_id
            subscription_ops = SubscriptionOps(db.session)
            subscription = subscription_ops.get_active_subscription(user_id)

            # 如果有活跃的订阅，将其设置为已取消
            if subscription:
                current_app.logger.debug(f"Setting subscription to cancelled for user {user_id}")
                subscription_ops.cancel_subscription(subscription.id)

                # 更新用户账号类型
                user_ops = UserOps(db.session)
                user_ops.update_account_type(user_id, 'free')

        elif event_type == 'transaction.refunded':
            # 支付退款
            current_app.logger.debug(f"Payment refunded for order {order_id}")

            # 更新订单状态
            order.status = OrderStatus.CANCELLED.value
            db.session.commit()

            # 如果是订阅订单，取消订阅
            if order.order_type == OrderType.SUBSCRIPTION.value:
                user_id = order.user_id
                subscription_ops = SubscriptionOps(db.session)
                subscription = subscription_ops.get_subscription_by_order(order_id)

                if subscription:
                    current_app.logger.debug(f"Cancelling subscription for user {user_id} due to refund")
                    subscription_ops.cancel_subscription(subscription.id)

                    # 更新用户账号类型
                    user_ops = UserOps(db.session)
                    user_ops.update_account_type(user_id, 'free')

            # 如果是积分购买，处理积分回收（如果可能）
            # 这里需要根据您的业务逻辑来实现

        current_app.logger.info(f"Successfully processed Paddle event: {event_type} for order {order_id}")
        return "true"  # Paddle期望收到一个简单的"true"作为成功响应
    except Exception as e:
        current_app.logger.error(f"Error handling Paddle webhook: {str(e)}", exc_info=True)
        return "false", 500


def process_successful_payment(order):
    """处理支付成功的订单"""
    try:
        order_data = order.to_dict()
        user_id = order_data['user_id']
        order_type = order_data['order_type']

        current_app.logger.debug(f"Processing Paddle payment for order type: {order_type}, user: {user_id}")

        extra_data = json.loads(order_data['extra_data']) if order_data['extra_data'] else {}
        current_app.logger.debug(f"Order extra data: {extra_data}")

        if order_type == OrderType.POINTS_PURCHASE.value:
            # 处理积分购买订单
            points_amount = extra_data.get('points', 0)
            current_app.logger.debug(f"Processing points purchase: {points_amount} points")

            if points_amount > 0:
                points_ops = PointsOps(db.session)
                success = points_ops.purchase_points(
                    user_id=user_id,
                    points_amount=points_amount,
                    payment_amount=order_data['amount'],
                    payment_order_id=order_data['order_id'],
                    payment_method=order_data['payment_method']
                )
                current_app.logger.debug(f"Points purchase processing result: {'success' if success else 'failed'}")

                if success:
                    current_app.logger.info(f"Added {points_amount} points for user {user_id}")
        elif order_type == OrderType.SUBSCRIPTION.value:
            # 处理会员订阅订单
            subscription_type = extra_data.get('subscription_type')
            current_app.logger.debug(f"Processing subscription: {subscription_type}")

            if subscription_type:
                # 创建订阅记录
                subscription_ops = SubscriptionOps(db.session)
                subscription = subscription_ops.create_subscription(
                    user_id=user_id,
                    subscription_type=subscription_type,
                    payment_amount=order_data['amount'],
                    payment_method=order_data['payment_method'],
                    payment_order_id=order_data['order_id']
                )

                if subscription:
                    # 更新用户账户类型
                    from zchat.models.subscription import AccountType
                    user_ops = UserOps(db.session)
                    account_type = AccountType.BASIC.value if subscription_type == SubscriptionType.BASIC.value else AccountType.PRO.value
                    user_ops.update_account_type(
                        id=user_id,
                        account_type=account_type,
                        subscription_start_time=subscription.start_time,
                        subscription_end_time=subscription.end_time
                    )
                    current_app.logger.info(f"Created subscription for user {user_id}: {subscription_type}")
    except Exception as e:
        current_app.logger.error(f"Error processing successful payment: {str(e)}", exc_info=True)


# 初始化Blueprint
def init_app(app):
    app.register_blueprint(bp)