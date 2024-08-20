import os

from flask import Flask, send_from_directory, request, current_app

def init_app(app):
    @app.route('/static/images/<path:filename>')
    def serve_image(filename):
        current_app.logger.debug(f'hello, {filename}')

        return send_from_directory(os.path.join(app.root_path, 'static', 'images'), filename)

    @app.after_request
    def add_header(response):
        if request.path.startswith('/static/images/'):
            # 设置Cache-Control头，max-age为1天（86400秒）
            response.headers['Cache-Control'] = 'public, max-age=86400'
        return response

