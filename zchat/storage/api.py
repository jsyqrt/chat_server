from flask import current_app
from typing import Dict, List, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

def init_app(app):
    """初始化应用

    Args:
        app: Flask应用
    """
    from .service import DocumentStoreService

    # 创建文档存储服务
    document_store = DocumentStoreService(app)

    # 创建初始集合
    create_initial_collections(app)

    # 应用上下文处理 - 不再关闭连接，只记录日志
    @app.teardown_appcontext
    def handle_teardown(exception):
        logger.debug("应用上下文已结束")

    # 请求后处理器 - 确保写入操作完成但不关闭连接
    @app.after_request
    def ensure_db_writes(response):
        if hasattr(app, 'document_store') and hasattr(app.document_store, 'store'):
            if hasattr(app.document_store.store, 'ensure_writes'):
                try:
                    # 同步数据到磁盘，确保数据持久化
                    app.document_store.store.ensure_writes()
                except Exception as e:
                    logger.warning(f"确保数据写入完成失败: {str(e)}")
        return response

    # 进程终止时的清理 - 使用atexit确保关闭连接
    import atexit

    def close_db_on_exit():
        """在进程退出时关闭数据库连接"""
        if hasattr(app, 'document_store') and hasattr(app.document_store, 'store'):
            if hasattr(app.document_store.store, 'close'):
                try:
                    app.document_store.store.close()
                    logger.info("进程退出时关闭数据库连接")
                except Exception as e:
                    logger.error(f"进程退出时关闭数据库连接失败: {str(e)}")

    # 注册进程退出处理函数
    atexit.register(close_db_on_exit)

    # 初始化健康检查端点
    @app.route('/api/db/health', methods=['GET'])
    def db_health():
        """数据库健康检查端点"""
        try:
            # 检查数据库连接
            if hasattr(app, 'document_store') and hasattr(app.document_store, 'store'):
                store = app.document_store.store
                if hasattr(store, '_get_connection'):
                    # 执行简单的连接检查
                    conn = store._get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT 1')
                    cursor.fetchone()
                    return {'status': 'ok', 'message': '数据库连接正常'}, 200

            return {'status': 'error', 'message': '数据库连接异常'}, 500
        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            return {'status': 'error', 'message': f'数据库健康检查失败: {str(e)}'}, 500

    # 添加MongoDB连接监控端点
    @app.route('/api/db/mongodb/stats', methods=['GET'])
    def mongodb_stats():
        """MongoDB连接统计信息端点"""
        try:
            # 检查文档存储类型是否为MongoDB
            store_type = app.config.get('DOCUMENT_STORE_TYPE')
            if store_type != 'mongodb':
                return {'status': 'error', 'message': f'当前存储类型不是MongoDB: {store_type}'}, 400

            # 获取MongoDB连接统计信息
            if hasattr(app, 'document_store') and hasattr(app.document_store, 'store'):
                store = app.document_store.store
                if hasattr(store, 'get_connection_stats'):
                    stats = store.get_connection_stats()
                    return {'status': 'ok', 'stats': stats}, 200
                else:
                    return {'status': 'error', 'message': 'MongoDB存储实例不支持获取连接统计信息'}, 500

            return {'status': 'error', 'message': '文档存储未初始化'}, 500
        except Exception as e:
            logger.error(f"获取MongoDB连接统计信息失败: {str(e)}")
            return {'status': 'error', 'message': f'获取MongoDB连接统计信息失败: {str(e)}'}, 500

def create_initial_collections(app):
    """创建初始集合

    Args:
        app: Flask应用
    """
    try:
        create_mindmaps_collection(app)
        create_favorites_collection(app)
        create_file_records_collection(app)
        logger.info("成功创建初始集合")
    except Exception as e:
        logger.error(f"创建初始集合失败: {str(e)}")
    return

# --- 思维导图 ---

def create_mindmaps_collection(app):
    """创建思维导图集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections.get('collections', []):
        if collection['name'] == 'mindmaps':
            exists = True
            break

    if not exists:
        app.logger.debug(f"创建思维导图集合")
        app.document_store.create_collection(
            collection_name='mindmaps',
            options={
                'primaryKey': 'id',
                'indexedFields': ['created_by', 'updated_at', 'created_at', 'title', 'roadmap_id']
            }
        )
        app.logger.debug(f"思维导图集合创建完成")
    else:
        app.logger.debug(f"思维导图集合已存在")
    return

def create_favorites_collection(app):
    """创建用户收藏集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections.get('collections', []):
        if collection['name'] == 'favorites':
            exists = True
            break

    if not exists:
        app.logger.debug(f"创建用户收藏集合")
        app.document_store.create_collection(
            collection_name='favorites',
            options={
                'primaryKey': 'user_id',
            }
        )
        app.logger.debug(f"用户收藏集合创建完成")
    else:
        app.logger.debug(f"用户收藏集合已存在")
    return

def create_file_records_collection(app):
    """创建文件记录集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections.get('collections', []):
        if collection['name'] == 'file_records':
            exists = True
            break

    if not exists:
        app.logger.debug(f"创建文件记录集合")
        app.document_store.create_collection(
            collection_name='file_records',
            options={
                'primaryKey': 'user_id',
            }
        )
        app.logger.debug(f"文件记录集合创建完成")
    else:
        app.logger.debug(f"文件记录集合已存在")
    return

def add_file_records(app, file_records: Dict[str, Any]) -> Dict[str, Any]:
    """添加文件记录

    Args:
        app: Flask应用
        file_records: 文件记录

    Returns:
        操作结果
    """
    try:
        return app.document_store.add_document('file_records', file_records)
    except Exception as e:
        logger.error(f"添加文件记录失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_file_records(app, user_id: str) -> Dict[str, Any]:
    """获取文件记录

    Args:
        app: Flask应用
        user_id: 用户ID
    """
    try:
        result = app.document_store.get_document('file_records', user_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取文件记录失败: {str(e)}")
        return {}

def update_file_records(app, file_records: Dict[str, Any]) -> Dict[str, Any]:
    """更新文件记录

    Args:
        app: Flask应用
        file_records: 文件记录

    Returns:
        操作结果
    """
    try:
        return app.document_store.update_document('file_records', file_records)
    except Exception as e:
        logger.error(f"更新文件记录失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def add_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """添加思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    try:
        return app.document_store.add_document('mindmaps', mindmap)
    except Exception as e:
        logger.error(f"添加思维导图失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def update_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """更新思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    try:
        return app.document_store.update_document('mindmaps', mindmap)
    except Exception as e:
        logger.error(f"更新思维导图失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """获取思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        思维导图
    """
    try:
        result = app.document_store.get_document('mindmaps', mindmap_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取思维导图失败: {str(e)}")
        return {}

def delete_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """删除思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        操作结果
    """
    try:
        return app.document_store.delete_document('mindmaps', mindmap_id)
    except Exception as e:
        logger.error(f"删除思维导图失败: {str(e)}")
        return {"status": "error", "message": str(e)}

# --- 用户思维导图状态 ---

def create_user_mindmap_status_collection(app, user_id: str) -> Dict[str, Any]:
    """创建用户思维导图状态集合

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        操作结果
    """
    collection_name = f'user_mindmap_status_{user_id}'

    # 检查集合是否已存在
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections.get('collections', []):
        if collection['name'] == collection_name:
            exists = True
            break

    if not exists:
        # 创建集合，指定主键为 mindmap_id 并添加索引字段
        try:
            return app.document_store.create_collection(
                collection_name=collection_name,
                options={
                    'primaryKey': 'mindmap_id',
                    'indexedFields': ['updated_at']
                }
            )
        except Exception as e:
            logger.error(f"创建用户思维导图状态集合失败: {str(e)}")
            return {"status": "error", "message": str(e)}

    return {"status": "success", "message": f"Collection {collection_name} already exists"}

def add_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """添加用户思维导图状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    try:
        create_user_mindmap_status_collection(app, user_id)
        index_name = f'user_mindmap_status_{user_id}'
        return app.document_store.add_document(index_name, mindmap_status)
    except Exception as e:
        logger.error(f"添加用户思维导图状态失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def update_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户思维导图状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    try:
        create_user_mindmap_status_collection(app, user_id)
        index_name = f'user_mindmap_status_{user_id}'
        return app.document_store.update_document(index_name, mindmap_status)
    except Exception as e:
        logger.error(f"更新用户思维导图状态失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_learning_status(app, user_id: str, mindmap_id: str) -> Dict[str, Any]:
    """获取学习状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_id: 思维导图ID

    Returns:
        学习状态
    """
    try:
        create_user_mindmap_status_collection(app, user_id)
        index_name = f'user_mindmap_status_{user_id}'
        result = app.document_store.get_document(index_name, mindmap_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取学习状态失败: {str(e)}")
        return {}

def get_learning_list(app, user_id: str, offset: int = 0, limit: int = 3) -> List[Dict[str, Any]]:
    """获取学习列表

    Args:
        app: Flask应用
        user_id: 用户ID
        offset: 偏移量
        limit: 限制

    Returns:
        学习列表
    """
    try:
        create_user_mindmap_status_collection(app, user_id)
        index_name = f'user_mindmap_status_{user_id}'
        result = app.document_store.search(index_name, '', {
            'offset': offset,
            'limit': limit,
            'sort': ['updated_at:desc']
        })
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"获取学习列表失败: {str(e)}")
        return []

# 搜索函数
def find_mindmaps_for_title(app, title: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按主题查找思维导图

    Args:
        app: Flask应用
        topic: 主题
        limit: 限制

    Returns:
        思维导图列表
    """
    try:
        index_name = 'mindmaps'
        result = app.document_store.search(index_name, '', {'filter': [f'title={title}'], 'limit': limit})
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"按主题查找思维导图失败: {str(e)}")
        return []

def find_user_mindmaps_created_by(app, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按用户查找思维导图

    Args:
        app: Flask应用
        user_id: 用户ID
        limit: 限制

    Returns:
        思维导图列表
    """
    try:
        index_name = 'mindmaps'
        result = app.document_store.search(index_name, '', {'filter': [f'created_by={user_id}'], 'limit': limit})
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"按用户查找思维导图失败: {str(e)}")
        return []

def upsert_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """更新或插入用户思维导图状态

    如果状态已存在则更新，否则插入新状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    try:
        create_user_mindmap_status_collection(app, user_id)
        index_name = f'user_mindmap_status_{user_id}'

        # 检查文档是否存在
        if 'mindmap_id' not in mindmap_status:
            return {"status": "error", "message": "mindmap_id is required"}

        mindmap_id = mindmap_status['mindmap_id']
        existing = app.document_store.search(index_name, '', {'filter': [f'mindmap_id={mindmap_id}']})

        # 更新时间戳
        now = time.time()
        mindmap_status_with_timestamp = mindmap_status.copy()
        mindmap_status_with_timestamp['updated_at'] = now

        if existing and len(existing.get('hits', [])) > 0:
            # 文档存在，更新它
            return app.document_store.update_document(index_name, mindmap_status_with_timestamp)
        else:
            # 文档不存在，添加它
            if 'created_at' not in mindmap_status_with_timestamp:
                mindmap_status_with_timestamp['created_at'] = now
            return app.document_store.add_document(index_name, mindmap_status_with_timestamp)
    except Exception as e:
        logger.error(f"更新用户思维导图状态失败: {str(e)}")
        return {"status": "error", "message": str(e)}

# --- 用户收藏 ---

def set_favorites(app, user_id: str, favorites: Dict[str, Any]) -> Dict[str, Any]:
    """设置用户收藏

    Args:
        app: Flask应用
        user_id: 用户ID
        favorites: 收藏

    Returns:
        操作结果
    """
    try:
        existing = app.document_store.get_document('favorites', user_id)
        data = {
            'user_id': user_id,
            'favorites': favorites
        }

        if existing:
            return app.document_store.update_document('favorites', data)
        else:
            return app.document_store.add_document('favorites', data)
    except Exception as e:
        logger.error(f"设置用户收藏失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_favorites(app, user_id: str) -> Dict[str, Any]:
    """获取用户收藏

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        收藏列表
    """
    try:
        result = app.document_store.get_document('favorites', user_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取用户收藏失败: {str(e)}")
        return {}

# --- 用户报告 ---

def create_user_assessment_report_collection(app, user_id: str) -> Dict[str, Any]:
    """创建用户报告集合

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        操作结果
    """
    try:
        collections = app.document_store.list_collections()
        exists = False
        for collection in collections.get('collections', []):
            if collection['name'] == f'user_assessment_report_{user_id}':
                exists = True
                break

        if not exists:
            return app.document_store.create_collection(
                collection_name=f'user_assessment_report_{user_id}',
                options={
                    'primaryKey': 'report_id',
                    'indexedFields': ['created_at', 'assessment_type']
                }
            )
        return {"status": "success", "message": f"Collection user_assessment_report_{user_id} already exists"}
    except Exception as e:
        logger.error(f"创建用户报告集合失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def add_user_assessment_report(app, user_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """添加用户报告

    Args:
        app: Flask应用
        user_id: 用户ID
        report: 报告

    Returns:
        操作结果
    """
    try:
        create_user_assessment_report_collection(app, user_id)
        index_name = f'user_assessment_report_{user_id}'
        return app.document_store.add_document(index_name, report)
    except Exception as e:
        logger.error(f"添加用户报告失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_user_assessment_report(app, user_id: str, report_id: str) -> Dict[str, Any]:
    """获取用户报告

    Args:
        app: Flask应用
        user_id: 用户ID
        report_id: 报告ID

    Returns:
        用户报告
    """
    try:
        index_name = f'user_assessment_report_{user_id}'
        result = app.document_store.get_document(index_name, report_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取用户报告失败: {str(e)}")
        return {}

def get_user_assessment_report_list(app, user_id: str, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """获取用户报告列表

    Args:
        app: Flask应用
        user_id: 用户ID
        offset: 偏移量
        limit: 限制

    Returns:
        用户报告列表
    """
    try:
        create_user_assessment_report_collection(app, user_id)
        index_name = f'user_assessment_report_{user_id}'
        result = app.document_store.search(index_name, '', {
            'offset': offset,
            'limit': limit,
            'sort': ['created_at:desc']
        })
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"获取用户报告列表失败: {str(e)}")
        return []

def create_feedback_collection(app):
    """创建反馈集合

    Args:
        app: Flask应用
    """
    try:
        collections = app.document_store.list_collections()
        exists = False
        for collection in collections.get('collections', []):
            if collection['name'] == 'feedback':
                exists = True
                break

        if not exists:
            app.document_store.create_collection(
                collection_name='feedback',
                options={
                    'primaryKey': 'id',
                    'indexedFields': ['created_at', 'created_by', 'category', 'status']
                }
            )
        return {"status": "success", "message": "Collection feedback already exists or created"}
    except Exception as e:
        logger.error(f"创建反馈集合失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def add_feedback(app, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """添加反馈

    Args:
        app: Flask应用
        feedback: 反馈

    Returns:
        操作结果
    """
    try:
        create_feedback_collection(app)
        index_name = 'feedback'
        return app.document_store.add_document(index_name, feedback)
    except Exception as e:
        logger.error(f"添加反馈失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_feedback(app, feedback_id: str) -> Dict[str, Any]:
    """获取反馈

    Args:
        app: Flask应用
        feedback_id: 反馈ID
    """
    try:
        create_feedback_collection(app)
        index_name = 'feedback'
        result = app.document_store.get_document(index_name, feedback_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取反馈失败: {str(e)}")
        return {}

def update_feedback(app, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """更新反馈

    Args:
        app: Flask应用
        feedback: 反馈
    """
    try:
        create_feedback_collection(app)
        index_name = 'feedback'
        return app.document_store.update_document(index_name, feedback)
    except Exception as e:
        logger.error(f"更新反馈失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_feedback_list(app, status: str = 'pending', offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """获取反馈列表

    Args:
        app: Flask应用
        status: 状态
        offset: 偏移量
        limit: 限制

    Returns:
        反馈列表
    """
    try:
        create_feedback_collection(app)
        index_name = 'feedback'
        result = app.document_store.search(index_name, '', {'filter': [f'status={status}'], 'offset': offset, 'limit': limit})
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"获取反馈列表失败: {str(e)}")
        return []

def create_jd_records_collection(app, user_id: str):
    """创建职位描述记录集合

    Args:
        app: Flask应用
        user_id: 用户ID
    """
    try:
        collection_name = f'jd_records_{user_id}'

        collections = app.document_store.list_collections()
        exists = False
        for collection in collections.get('collections', []):
            if collection['name'] == collection_name:
                exists = True
                break

        if not exists:
            app.document_store.create_collection(
                collection_name=collection_name,
                options={
                    'primaryKey': 'id',
                    'indexedFields': ['created_at', 'updated_at', 'job_title', 'company']
                }
            )
        return {"status": "success", "message": f"Collection {collection_name} already exists or created"}
    except Exception as e:
        logger.error(f"创建职位描述记录集合失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def add_jd_record(app, user_id: str, jd_record: Dict[str, Any]) -> Dict[str, Any]:
    """添加职位描述记录

    Args:
        app: Flask应用
        user_id: 用户ID
        jd_record: 职位描述记录

    Returns:
        操作结果
    """
    try:
        create_jd_records_collection(app, user_id)
        index_name = f'jd_records_{user_id}'
        return app.document_store.add_document(index_name, jd_record)
    except Exception as e:
        logger.error(f"添加职位描述记录失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_jd_record(app, user_id: str, jd_id: str) -> Dict[str, Any]:
    """获取职位描述记录

    Args:
        app: Flask应用
        user_id: 用户ID
        jd_id: 职位描述记录ID

    Returns:
        职位描述记录
    """
    try:
        index_name = f'jd_records_{user_id}'
        result = app.document_store.get_document(index_name, jd_id)
        return result if result else {}
    except Exception as e:
        logger.error(f"获取职位描述记录失败: {str(e)}")
        return {}

def get_jd_records(app, user_id: str, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """获取职位描述记录列表

    Args:
        app: Flask应用
        user_id: 用户ID
        offset: 偏移量
        limit: 限制

    Returns:
        职位描述记录列表
    """
    try:
        create_jd_records_collection(app, user_id)
        index_name = f'jd_records_{user_id}'
        result = app.document_store.search(index_name, '', {'offset': offset, 'limit': limit, 'sort': ['created_at:desc']})
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"获取职位描述记录列表失败: {str(e)}")
        return []

def create_resume_optimization_records_collection(app, user_id: str):
    """创建简历优化记录集合

    Args:
        app: Flask应用
        user_id: 用户ID
    """
    try:
        collection_name = f'resume_optimization_records_{user_id}'

        collections = app.document_store.list_collections()
        exists = False
        for collection in collections.get('collections', []):
            if collection['name'] == collection_name:
                exists = True
                break

        if not exists:
            app.document_store.create_collection(
                collection_name=collection_name,
                options={
                    'primaryKey': 'id',
                    'indexedFields': ['created_at', 'updated_at']
                }
            )
        return {"status": "success", "message": f"Collection {collection_name} already exists or created"}
    except Exception as e:
        logger.error(f"创建简历优化记录集合失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def add_resume_optimization_record(app, user_id: str, resume_optimization_record: Dict[str, Any]) -> Dict[str, Any]:
    """添加简历优化记录

    Args:
        app: Flask应用
        user_id: 用户ID
        resume_optimization_record: 简历优化记录
    """
    try:
        create_resume_optimization_records_collection(app, user_id)
        index_name = f'resume_optimization_records_{user_id}'
        return app.document_store.add_document(index_name, resume_optimization_record)
    except Exception as e:
        logger.error(f"添加简历优化记录失败: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_resume_optimization_records(app, user_id: str, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """获取简历优化记录

    Args:
        app: Flask应用
        user_id: 用户ID
        offset: 偏移量
        limit: 限制

    Returns:
        简历优化记录列表
    """
    try:
        create_resume_optimization_records_collection(app, user_id)
        index_name = f'resume_optimization_records_{user_id}'
        result = app.document_store.search(index_name, '', {'offset': offset, 'limit': limit, 'sort': ['created_at:desc']})
        return result.get('hits', [])
    except Exception as e:
        logger.error(f"获取简历优化记录失败: {str(e)}")
        return []

# --- 危险操作！仅供管理员使用 ---
def delete_collection(app, collection_name: str) -> Dict[str, Any]:
    """删除集合

    Args:
        app: Flask应用
        collection_name: 集合名称

    Returns:
        操作结果
    """
    try:
        return app.document_store.delete_collection(collection_name)
    except Exception as e:
        logger.error(f"删除集合{collection_name}失败: {str(e)}")
        return {"status": "error", "message": str(e)}

