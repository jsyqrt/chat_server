from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, current_app, g, session, jsonify
import json
from flask_login import current_user

from zchat.models.base import db
from zchat.models.payment import PaymentOrderOps, OrderStatus
from zchat.models.user import UserOps
from zchat.models.subscription import SubscriptionOps
from zchat.models.points import PointsOps

bp = Blueprint('website', __name__)

# @bp.route('/')
# def index():
#     """Voylead官网首页"""
#     return render_template('index.html')

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(current_app.static_folder, 'favicon.ico')

@bp.route('/payment')
def payment_success():
    """支付成功页面"""
    # 获取URL参数
    transaction_id = request.args.get('transaction_id')
    customer_email = request.args.get('customer_email')
    paddle_customer_id = request.args.get('paddle_customer_id')

    current_app.logger.debug(f"Payment success page accessed: transaction_id={transaction_id}, email={customer_email}, customer_id={paddle_customer_id}")

    # 查询交易信息
    payment_ops = PaymentOrderOps(db.session)
    order = None

    # 尝试通过paddle_payment_id查找订单
    orders = payment_ops.find_orders_by_paddle_info(transaction_id=transaction_id)

    if orders:
        # 找到了关联的订单
        order = orders[0]
        current_app.logger.debug(f"Found order: {order.order_id}")

        # 获取订单相关信息
        order_data = order.to_dict()
        user_id = order_data['user_id']
        order_type = order_data['order_type']

        # 获取用户信息
        user_ops = UserOps(db.session)
        user = user_ops.get_one(user_id)
        username = user.nickname or user.username if user else "Unknown User"

        # 解析订单额外数据
        extra_data = json.loads(order_data['extra_data']) if order_data['extra_data'] else {}

        # 获取订单商品信息
        purchase_detail = {}

        if order_type == 'points_purchase':
            # 积分购买订单
            points_amount = extra_data.get('points', 0)
            purchase_detail = {
                'type': 'points',
                'points': points_amount,
                'price': order_data['amount'],
                'title': f"购买{points_amount}积分"
            }
        elif order_type == 'subscription':
            # 会员订阅订单
            subscription_type = extra_data.get('subscription_type')

            # 获取订阅信息
            subscription_ops = SubscriptionOps(db.session)
            subscription = subscription_ops.get_subscription_by_order(order_data['order_id'])

            if subscription:
                sub_data = subscription.to_dict()
                purchase_detail = {
                    'type': 'subscription',
                    'subscription_type': subscription_type,
                    'price': order_data['amount'],
                    'start_time': sub_data['start_time'],
                    'end_time': sub_data['end_time'],
                    'title': f"{subscription_type}会员订阅"
                }
            else:
                purchase_detail = {
                    'type': 'subscription',
                    'subscription_type': subscription_type,
                    'price': order_data['amount'],
                    'title': f"{subscription_type}会员订阅"
                }

        # 准备模板数据
        template_data = {
            'transaction_id': transaction_id,
            'customer_email': customer_email,
            'paddle_customer_id': paddle_customer_id,
            'order': order_data,
            'username': username,
            'purchase_detail': purchase_detail,
            'payment_status': order_data['status'],
            'payment_success': order_data['status'] == OrderStatus.PAID.value,
        }

        return render_template('payment_success.html', **template_data)
    else:
        # 找不到订单信息，显示通用成功页面
        current_app.logger.warning(f"No order found for transaction {transaction_id}")
        return render_template('payment_success.html',
                              transaction_id=transaction_id,
                              customer_email=customer_email,
                              paddle_customer_id=paddle_customer_id,
                              payment_success=True,
                              no_order_found=True)

@bp.route('/download')
def download():
    """下载页面，可根据设备自动重定向到相应的应用商店"""
    user_agent = request.user_agent.string.lower()

    # 检测设备类型
    if 'iphone' in user_agent or 'ipad' in user_agent or 'ipod' in user_agent:
        # iOS设备 - 跳转到App Store
        return redirect('https://apps.apple.com/cn/app/职路/id123456789')
    elif 'android' in user_agent:
        # 检测Android设备品牌
        if any(brand in user_agent for brand in ['mi ', 'redmi', 'hm note', 'mix ']):
            # 小米设备 - 跳转到小米应用商店
            return redirect('https://app.mi.com/details?id=com.zhilu.app')
        elif any(brand in user_agent for brand in ['oppo', 'pafm', 'pbfm', 'pcrm']):
            # OPPO设备 - 跳转到OPPO应用商店
            return redirect('https://store.oppomobile.com/search?keyword=职路')
        elif 'huawei' in user_agent or 'honor' in user_agent:
            # 华为设备 - 跳转到华为应用商店
            return redirect('https://appgallery.huawei.com/search/职路')
        elif 'vivo' in user_agent:
            # vivo设备 - 跳转到vivo应用商店
            return redirect('https://info.appstore.vivo.com.cn/detail/职路')
        else:
            # 其他Android设备 - 跳转到应用宝（比Google Play更适合中国用户）
            return redirect('https://a.app.qq.com/o/simple.jsp?pkgname=com.zhilu.app')
    else:
        # 未知设备或桌面设备 - 显示下载页面
        return redirect(url_for('website.index', _anchor='download'))

@bp.route('/switch_language/<lang>')
def switch_language(lang):
    if lang in ['en', 'zh_CN']:
        current_app.logger.info(f"Switching language to {lang}")
        session['lang'] = lang
    return redirect(request.referrer or url_for('website.index'))