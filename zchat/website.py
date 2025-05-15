from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, current_app, g, session

bp = Blueprint('website', __name__)

@bp.route('/')
def index():
    """Voylead官网首页"""
    return render_template('index.html')

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(current_app.static_folder, 'favicon.ico')

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