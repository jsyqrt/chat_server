import json
import time
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from zchat.models.base import db
from zchat.models.user import UserOps
from zchat.models.payment import PaymentOrderOps, OrderStatus, OrderType
from zchat.models.points import PointsOps
from zchat.models.subscription import SubscriptionOps, SubscriptionType
from zchat.utils.alipay_utils import AlipayService

# 创建蓝图
bp = Blueprint('alipay', __name__, url_prefix='/alipay')

@bp.route('/notify', methods=['POST'])
def alipay_notify():
    """支付宝异步通知接口"""
    try:
        # 解析通知数据
        data = AlipayService.parse_notification_data(request)
        current_app.logger.debug(f"Received Alipay notification: {data}")

        # 验证通知的真实性
        verify_result = AlipayService.verify_async_notification(data)
        current_app.logger.debug(f"Notification verification result: {verify_result}")

        if not verify_result:
            current_app.logger.warning("Alipay notification verification failed")
            return "failure", 400

        # 提取订单信息
        out_trade_no = data.get('out_trade_no')  # 商户订单号
        trade_no = data.get('trade_no')          # 支付宝交易号
        trade_status = data.get('trade_status')  # 交易状态
        total_amount = data.get('total_amount')  # 交易金额

        current_app.logger.debug(f"Notification for order {out_trade_no}, trade_no: {trade_no}, status: {trade_status}, amount: {total_amount}")

        # 获取订单信息
        payment_ops = PaymentOrderOps(db.session)
        order = payment_ops.get_order_by_id(out_trade_no)

        if not order:
            current_app.logger.warning(f"Order not found: {out_trade_no}")
            return "failure", 404

        # 检查订单状态
        current_app.logger.debug(f"Current order status: {order.status}")

        if order.status == OrderStatus.PAID.value:
            # 订单已支付，避免重复处理
            current_app.logger.debug(f"Order {out_trade_no} already paid, skipping processing")
            return "success"

        # 检查交易状态是否表示支付成功
        payment_successful = AlipayService.is_payment_successful(trade_status)
        current_app.logger.debug(f"Is payment successful: {payment_successful}")

        if payment_successful:
            # 更新订单状态
            current_app.logger.debug(f"Updating order {out_trade_no} status to PAID")
            payment_ops.update_order_status(
                order_id=out_trade_no,
                status=OrderStatus.PAID.value,
                transaction_id=trade_no
            )

            # 根据订单类型处理后续逻辑
            current_app.logger.debug(f"Processing successful payment for order {out_trade_no}")
            process_successful_payment(order)

            current_app.logger.info(f"Payment successful for order: {out_trade_no}")
            return "success"
        else:
            # 支付未成功
            current_app.logger.debug(f"Updating order {out_trade_no} status to FAILED")
            payment_ops.update_order_status(
                order_id=out_trade_no,
                status=OrderStatus.FAILED.value
            )
            current_app.logger.info(f"Payment failed for order: {out_trade_no}, status: {trade_status}")
            return "success"
    except Exception as e:
        current_app.logger.error(f"Error handling Alipay notification: {str(e)}", exc_info=True)
        return "failure", 500

def process_successful_payment(order):
    """处理支付成功的订单"""
    try:
        order_data = order.to_dict()
        user_id = order_data['user_id']
        order_type = order_data['order_type']

        current_app.logger.debug(f"Processing payment for order type: {order_type}, user: {user_id}")

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