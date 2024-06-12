import string
import random
import os

def random_bool():
    return random.choices([True, False])[0]

def random_name(length=15):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def random_phone_number():
    numbers = string.digits
    return '13' + ''.join(random.choices(numbers, k=9))

def random_gender():
    values = ['未知', '男', '女']
    return random.choices(values)[0]

def random_edubg():
    values = [
        '未知',
        '大专',
        '本科',
        '硕士',
        '博士',
    ]
    return random.choices(values)[0]

def random_yearofwork():
    values = [
        '未知',
        "少于1年",
        "1年",
        "2年",
        "3到5年",
        "5到10年",
        "10年以上",
    ]
    return random.choices(values)[0]

def random_signature():
    return ' '.join([random_name() for i in range(10)])

def random_avatar(image_dir):
    values = os.listdir(image_dir)
    v = random.choices(values)[0]
    if v.endswith('.jpg'):
        return v
    else:
        return random_avatar(image_dir=image_dir)

def random_email(name, company):
    values = [
        'cc',
        'com',
        'org',
        'cn',
    ]
    return f'{name}@{company}.{random.choices(values)[0]}'

def random_company():
    values = [
        '万科企业股份有限公司',
        '恒大集团有限公司',
        '碧桂园控股有限公司',
        '海航集团有限公司',
        '华为技术有限公司',
        '正威集团有限公司',
        '苏宁控股集团有限公司',
        '阿里巴巴集团控股有限公司',
        '恒大汽车集团有限公司',
        '广东温氏食品集团股份有限公司',
        '中国通向国际集团有限公司',
        '海尔集团公司',
        '融创中国控股有限公司',
        '京东集团',
        '万达集团有限公司',
        '步步高商业连锁股份有限公司',
        '顺丰控股股份有限公司',
        '吉利控股集团有限公司',
        '中国圣牧有机奶业集团有限公司',
        '统一企业中国有限公司',
        '华侨城集团有限公司',
        '复星国际有限公司',
        '美的集团股份有限公司',
        '广东明珠集团股份有限公司',
        '中国恒大集团有限公司',
        '中国宝安集团股份有限公司',
        '春兴精工股份有限公司',
        '首钢集团有限公司',
        '三一重工股份有限公司',
        '万向集团公司',
        '深圳市怡亚通供应链股份有限公司',
        '招商局集团有限公司',
        '华塑控股股份有限公司',
        '华能国际电力股份有限公司',
        '浙江吉利控股集团有限公司',
        '北京亿城集团有限公司',
        '招商局能源运输股份有限公司',
        '海信集团有限公司',
        '珠海格力电器股份有限公司',
        '大连万达集团股份有限公司',
        '中国宏桥集团有限公司',
        '九阳股份有限公司',
        '中国中冶集团有限公司',
        '安徽安凯汽车股份有限公司',
        '蒙牛乳业股份有限公司',
        '东风汽车公司',
        '四川长虹电器股份有限公司',
        '百度公司',
        '小米科技有限责任公司',
        '中国海螺集团有限公司',
    ]
    return random.choices(values)[0]

def random_title():
    values = [
        '软件工程师',
        '高级工程师',
        '技术专家',
        '高级技术专家',
        '技术总监',
    ]
    return random.choices(values)[0]

def random_profession():
    values = [
        'C++',
        '后端开发',
        '数据库内核',
        '前端',
        '操作系统优化',
    ]
    return random.choices(values)[0]

def random_business():
    values = [
        '电商',
        '直播',
        '短视频',
        '在线社区',
        '团购',
        '金融服务',
    ]
    return random.choices(values)[0]

def random_price():
    values = [
        500,
        600,
        700,
        800,
        900,
        1000,
        1500,
        2500,
        5000,
    ]
    return random.choices(values)[0]

def random_jd():
    return ' '.join([random_name() for i in range(30)])
