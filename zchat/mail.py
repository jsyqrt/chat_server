import os
import time
import uuid

from flask import current_app, render_template
from flask_mail import Mail, Message

mail = Mail()

def init_app(app):
    """初始化邮件服务"""
    mail.init_app(app)

def send_email(subject, recipients, html_body, text_body=None):
    """发送邮件，使用同步方式"""
    try:
        msg = Message(subject, recipients=recipients)
        msg.html = html_body
        if text_body:
            msg.body = text_body

        mail.send(msg)
        current_app.logger.info(f"Successfully sent email to {recipients}")
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {recipients}: {str(e)}")
        raise

def generate_verification_token():
    """生成验证令牌"""
    return str(uuid.uuid4())

def send_verification_email(user_id, email, token):
    """发送邮箱验证邮件"""
    try:
        # 构建验证链接
        site_url = current_app.config.get('SITE_URL', '')
        if not site_url:
            raise ValueError("SITE_URL configuration is missing")

        verification_url = f"{site_url}/auth/verify_email?user_id={user_id}&token={token}"

        # 邮件主题
        subject = "验证您的ZChat账号邮箱"

        # 邮件HTML内容
        html_body = f"""
        <p>您好，</p>
        <p>请点击下面的链接验证您的ZChat账号邮箱：</p>
        <p><a href="{verification_url}">{verification_url}</a></p>
        <p>如果您没有注册ZChat账号，请忽略此邮件。</p>
        <p>此邮件由系统自动发送，请勿回复。</p>
        """

        # 邮件纯文本内容
        text_body = f"""
        您好，

        请点击下面的链接验证您的ZChat账号邮箱：
        {verification_url}

        如果您没有注册ZChat账号，请忽略此邮件。

        此邮件由系统自动发送，请勿回复。
        """

        return send_email(subject, [email], html_body, text_body)
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email: {str(e)}")
        raise

def send_password_reset_email(email, token):
    """发送密码重置邮件"""
    # 构建重置链接
    reset_url = f"{current_app.config['SITE_URL']}/auth/reset_password?token={token}"

    # 邮件主题
    subject = "重置您的ZChat账号密码"

    # 邮件HTML内容
    html_body = f"""
    <p>您好，</p>
    <p>您请求重置ZChat账号密码。请点击下面的链接重置密码：</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>此链接1小时内有效。</p>
    <p>如果您没有请求重置密码，请忽略此邮件。</p>
    <p>此邮件由系统自动发送，请勿回复。</p>
    """

    # 邮件纯文本内容
    text_body = f"""
    您好，

    您请求重置ZChat账号密码。请点击下面的链接重置密码：
    {reset_url}

    此链接1小时内有效。

    如果您没有请求重置密码，请忽略此邮件。

    此邮件由系统自动发送，请勿回复。
    """

    return send_email(subject, [email], html_body, text_body)