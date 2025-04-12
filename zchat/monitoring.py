from flask import Blueprint, request, Response, current_app
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time  # Add import for time module
import traceback

bp = Blueprint('monitoring', __name__)

# 创建指标对象，全局变量，在init_app中初始化
metrics = None
http_request_total = None
http_request_duration_seconds = None
http_request_exceptions_total = None
active_users_gauge = None
db_query_duration = None
api_requests_total = None
error_rate = None

def init_app(app):
    """初始化监控模块"""
    global metrics, http_request_total, http_request_duration_seconds, http_request_exceptions_total
    global active_users_gauge, db_query_duration, api_requests_total, error_rate

    # 创建PrometheusMetrics实例
    metrics = PrometheusMetrics(app)

    # 自动收集默认指标
    metrics.info('app_info', 'Application info', version='1.0.0')

    # 自定义指标
    http_request_total = Counter(
        'http_request_total',
        'Total number of HTTP requests',
        ['method', 'endpoint', 'status']
    )

    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint'],
        buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, 100.0, float('inf'))
    )

    http_request_exceptions_total = Counter(
        'http_request_exceptions_total',
        'Total number of HTTP requests that resulted in exceptions',
        ['method', 'endpoint', 'exception_type']
    )

    active_users_gauge = Gauge(
        'active_users',
        'Number of active users',
        ['type']  # e.g., 'logged_in', 'anonymous'
    )

    db_query_duration = Histogram(
        'db_query_duration_seconds',
        'Database query duration in seconds',
        ['query_type'],
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, float('inf'))
    )

    api_requests_total = Counter(
        'api_requests_total',
        'Total number of API requests',
        ['api_name', 'status']
    )

    error_rate = Gauge(
        'error_rate',
        'Error rate over the last minute',
    )

    # 注册监控蓝图
    app.register_blueprint(bp, url_prefix='/metrics')

    # 监控请求前后
    @app.before_request
    def before_request():
        try:
            # Use time.time() instead of metrics._time()
            request.start_time = time.time()
        except Exception as e:
            app.logger.error(f"监控before_request错误: {str(e)}")
            # 不抛出异常，让请求继续处理

    @app.after_request
    def after_request(response):
        try:
            if hasattr(request, 'start_time'):
                # Use time.time() instead of metrics._time()
                request_latency = time.time() - request.start_time
                http_request_duration_seconds.labels(
                    method=request.method,
                    endpoint=request.endpoint or 'unknown'
                ).observe(request_latency)

                http_request_total.labels(
                    method=request.method,
                    endpoint=request.endpoint or 'unknown',
                    status=response.status_code
                ).inc()
        except Exception as e:
            app.logger.error(f"监控after_request错误: {str(e)}")
            # 不抛出异常，确保响应正常返回

        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        try:
            if hasattr(request, 'start_time'):
                http_request_exceptions_total.labels(
                    method=request.method,
                    endpoint=request.endpoint or 'unknown',
                    exception_type=type(e).__name__
                ).inc()
        except Exception as logging_error:
            app.logger.error(f"错误处理器中出现异常: {str(logging_error)}")

        # 继续传递异常
        raise e

@bp.route('/')
def metrics():
    """暴露所有指标的endpoint"""
    try:
        return Response(generate_latest(), mimetype='text/plain')
    except Exception as e:
        current_app.logger.error(f"生成指标数据时出错: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return Response("Error generating metrics", status=500, mimetype='text/plain')

# 用于记录数据库查询的上下文管理器
class DBQueryTimer:
    def __init__(self, query_type):
        self.query_type = query_type
        self.start_time = None

    def __enter__(self):
        try:
            # Use time.time() instead of metrics._time()
            self.start_time = time.time()
        except Exception as e:
            current_app.logger.error(f"DBQueryTimer.__enter__ 错误: {str(e)}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if db_query_duration and self.start_time is not None:
                # Use time.time() instead of metrics._time()
                query_latency = time.time() - self.start_time
                db_query_duration.labels(query_type=self.query_type).observe(query_latency)
        except Exception as e:
            current_app.logger.error(f"DBQueryTimer.__exit__ 错误: {str(e)}")
        # 不抑制异常传播
        return False

# 记录API请求的函数
def record_api_request(api_name, status):
    """记录API请求指标"""
    try:
        if api_requests_total:
            api_requests_total.labels(api_name=api_name, status=status).inc()
    except Exception as e:
        current_app.logger.error(f"记录API请求指标时出错: {str(e)}")

# 更新活跃用户数量
def update_active_users(count, user_type='logged_in'):
    """更新活跃用户数量指标"""
    try:
        if active_users_gauge:
            active_users_gauge.labels(type=user_type).set(count)
    except Exception as e:
        current_app.logger.error(f"更新活跃用户数量时出错: {str(e)}")

# 更新错误率
def update_error_rate(rate):
    """更新错误率指标"""
    try:
        if error_rate:
            error_rate.set(rate)
    except Exception as e:
        current_app.logger.error(f"更新错误率时出错: {str(e)}")