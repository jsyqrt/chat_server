from flask import current_app
from typing import Dict, List, Any, Optional
import time

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

    # 在应用关闭时关闭连接
    @app.teardown_appcontext
    def close_db(exception):
        if hasattr(app, 'document_store') and hasattr(app.document_store, 'store'):
            if hasattr(app.document_store.store, 'close'):
                app.document_store.store.close()

def create_initial_collections(app):
    """创建初始集合

    Args:
        app: Flask应用
    """
    create_mindmaps_collection(app)
    create_favorites_collection(app)
    create_file_records_collection(app)
    return

# --- 思维导图 ---

def create_mindmaps_collection(app):
    """创建思维导图集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections['collections']:
        if collection['name'] == 'mindmaps':
            exists = True
            break

    if not exists:
        app.document_store.create_collection(
            collection_name='mindmaps',
            options={
                'primaryKey': 'id',
                'indexedFields': ['created_by', 'updated_at', 'created_at', 'title', 'roadmap_id']
            }
        )
    return

def create_favorites_collection(app):
    """创建用户收藏集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections['collections']:
        if collection['name'] == 'favorites':
            exists = True
            break

    if not exists:
        app.document_store.create_collection(
            collection_name='favorites',
            options={
                'primaryKey': 'user_id',
            }
        )
    return

def create_file_records_collection(app):
    """创建文件记录集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections['collections']:
        if collection['name'] == 'file_records':
            exists = True
            break

    if not exists:
        app.document_store.create_collection(
            collection_name='file_records',
            options={
                'primaryKey': 'user_id',
            }
        )
    return

def add_file_records(app, file_records: Dict[str, Any]) -> Dict[str, Any]:
    """添加文件记录

    Args:
        app: Flask应用
        file_records: 文件记录

    Returns:
        操作结果
    """
    return app.document_store.add_document('file_records', file_records)

def get_file_records(app, user_id: str) -> Dict[str, Any]:
    """获取文件记录

    Args:
        app: Flask应用
        user_id: 用户ID
    """
    return app.document_store.get_document('file_records', user_id)

def update_file_records(app, file_records: Dict[str, Any]) -> Dict[str, Any]:
    """更新文件记录

    Args:
        app: Flask应用
        file_records: 文件记录

    Returns:
        操作结果
    """
    return app.document_store.update_document('file_records', file_records)

def add_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """添加思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    return app.document_store.add_document('mindmaps', mindmap)

def update_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """更新思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    return app.document_store.update_document('mindmaps', mindmap)

def get_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """获取思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        思维导图
    """
    result = app.document_store.get_document('mindmaps', mindmap_id)
    return result if result else {}

def delete_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """删除思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        操作结果
    """
    return app.document_store.delete_document('mindmaps', mindmap_id)

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
    for collection in collections['collections']:
        if collection['name'] == collection_name:
            exists = True
            break

    if not exists:
        # 创建集合，指定主键为 mindmap_id 并添加索引字段
        return app.document_store.create_collection(
            collection_name=collection_name,
            options={
                'primaryKey': 'mindmap_id',
                'indexedFields': ['updated_at']
            }
        )

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
    create_user_mindmap_status_collection(app, user_id)
    index_name = f'user_mindmap_status_{user_id}'
    return app.document_store.add_document(index_name, mindmap_status)

def update_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户思维导图状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    create_user_mindmap_status_collection(app, user_id)
    index_name = f'user_mindmap_status_{user_id}'
    return app.document_store.update_document(index_name, mindmap_status)

def get_learning_status(app, user_id: str, mindmap_id: str) -> Dict[str, Any]:
    """获取学习状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_id: 思维导图ID

    Returns:
        学习状态
    """
    create_user_mindmap_status_collection(app, user_id)
    index_name = f'user_mindmap_status_{user_id}'
    return app.document_store.get_document(index_name, mindmap_id)

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
    create_user_mindmap_status_collection(app, user_id)
    index_name = f'user_mindmap_status_{user_id}'
    result = app.document_store.search(index_name, '', {
        'offset': offset,
        'limit': limit,
        'sort': ['updated_at:desc']
    })
    return result['hits']

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
    index_name = 'mindmaps'
    return app.document_store.search(index_name, '', {'filter': [f'title={title}'], 'limit': limit})['hits']

def find_user_mindmaps_created_by(app, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按用户查找思维导图

    Args:
        app: Flask应用
        user_id: 用户ID
        limit: 限制

    Returns:
        思维导图列表
    """
    index_name = 'mindmaps'
    return app.document_store.search(index_name, '', {'filter': [f'created_by={user_id}'], 'limit': limit})['hits']

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
    existing = app.document_store.get_document('favorites', user_id)
    if existing:
        return app.document_store.update_document('favorites', {
            'user_id': user_id,
            'favorites': favorites
        })
    else:
        return app.document_store.add_document('favorites', {
            'user_id': user_id,
            'favorites': favorites
        })


def get_favorites(app, user_id: str) -> Dict[str, Any]:
    """获取用户收藏

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        收藏列表
    """
    return app.document_store.get_document('favorites', user_id)

# --- 用户报告 ---

def create_user_assessment_report_collection(app, user_id: str) -> Dict[str, Any]:
    """创建用户报告集合

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        操作结果
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections['collections']:
        if collection['name'] == f'user_assessment_report_{user_id}':
            exists = True
            break

    if not exists:
        app.document_store.create_collection(
            collection_name=f'user_assessment_report_{user_id}',
            options={
                'primaryKey': 'report_id',
                'indexedFields': ['created_at', 'assessment_type']
            }
        )
    return

def add_user_assessment_report(app, user_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """添加用户报告

    Args:
        app: Flask应用
        user_id: 用户ID
        report: 报告

    Returns:
        操作结果
    """
    create_user_assessment_report_collection(app, user_id)
    index_name = f'user_assessment_report_{user_id}'
    return app.document_store.add_document(index_name, report)

def get_user_assessment_report(app, user_id: str, report_id: str) -> Dict[str, Any]:
    """获取用户报告

    Args:
        app: Flask应用
        user_id: 用户ID
        report_id: 报告ID

    Returns:
        用户报告
    """
    index_name = f'user_assessment_report_{user_id}'
    return app.document_store.get_document(index_name, report_id)

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
    index_name = f'user_assessment_report_{user_id}'
    return app.document_store.search(index_name, '', {
        'offset': offset,
        'limit': limit,
        'sort': ['created_at:desc']
    })['hits']

def create_feedback_collection(app):
    """创建反馈集合

    Args:
        app: Flask应用
    """
    collections = app.document_store.list_collections()
    exists = False
    for collection in collections['collections']:
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
    return

def add_feedback(app, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """添加反馈

    Args:
        app: Flask应用
        feedback: 反馈

    Returns:
        操作结果
    """
    create_feedback_collection(app)
    index_name = 'feedback'
    return app.document_store.add_document(index_name, feedback)

def get_feedback(app, feedback_id: str) -> Dict[str, Any]:
    """获取反馈

    Args:
        app: Flask应用
        feedback_id: 反馈ID
    """
    create_feedback_collection(app)
    index_name = 'feedback'
    return app.document_store.get_document(index_name, feedback_id)

def update_feedback(app, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """更新反馈

    Args:
        app: Flask应用
        feedback: 反馈
    """
    create_feedback_collection(app)
    index_name = 'feedback'
    return app.document_store.update_document(index_name, feedback)

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
    create_feedback_collection(app)
    index_name = 'feedback'
    return app.document_store.search(index_name, '', {'filter': [f'status={status}'], 'offset': offset, 'limit': limit})['hits']

# --- 危险操作！仅供管理员使用 ---
def delete_collection(app, collection_name: str) -> Dict[str, Any]:
    """删除集合

    Args:
        app: Flask应用
        collection_name: 集合名称

    Returns:
        操作结果
    """
    return app.document_store.delete_collection(collection_name)

