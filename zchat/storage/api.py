from flask import current_app
from typing import Dict, List, Any, Optional

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
    return

def create_favorites_collection(app):
    """创建用户收藏集合

    Args:
        app: Flask应用
    """

    create_favorites_collection(app)
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
        app.document_store.create_collection('mindmaps', {'primaryKey': 'id'})
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
        app.document_store.create_collection('favorites', {'primaryKey': 'user_id'})
    return

def add_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """添加思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    return app.document_store.add_mindmap(mindmap)

def update_mindmap(app, mindmap: Dict[str, Any]) -> Dict[str, Any]:
    """更新思维导图

    Args:
        app: Flask应用
        mindmap: 思维导图

    Returns:
        操作结果
    """
    return app.document_store.update_mindmap(mindmap)

def get_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """获取思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        思维导图
    """
    result = app.document_store.get_mindmap(mindmap_id)
    return result if result else {}

def delete_mindmap(app, mindmap_id: str) -> Dict[str, Any]:
    """删除思维导图

    Args:
        app: Flask应用
        mindmap_id: 思维导图ID

    Returns:
        操作结果
    """
    return app.document_store.delete_mindmap(mindmap_id)

# --- 用户思维导图状态 ---

def create_user_mindmap_status_collection(app, user_id: str) -> Dict[str, Any]:
    """创建用户思维导图状态集合

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        操作结果
    """
    return app.document_store.create_user_mindmap_status_collection(user_id)

def add_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """添加用户思维导图状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    return app.document_store.add_user_mindmap_status(user_id, mindmap_status)

def update_user_mindmap_status(app, user_id: str, mindmap_status: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户思维导图状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_status: 思维导图状态

    Returns:
        操作结果
    """
    return app.document_store.update_user_mindmap_status(user_id, mindmap_status)

def get_learning_status(app, user_id: str, mindmap_id: str) -> Dict[str, Any]:
    """获取学习状态

    Args:
        app: Flask应用
        user_id: 用户ID
        mindmap_id: 思维导图ID

    Returns:
        学习状态
    """
    return app.document_store.get_user_mindmap_status(user_id, mindmap_id)

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
    return app.document_store.get_user_mindmap_status_list(user_id, offset, limit)

# 搜索函数
def find_mindmaps_for(app, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按主题查找思维导图

    Args:
        app: Flask应用
        topic: 主题
        limit: 限制

    Returns:
        思维导图列表
    """
    return app.document_store.find_mindmaps_by_topic(topic, limit)

def find_user_mindmaps_created_by(app, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按用户查找思维导图

    Args:
        app: Flask应用
        user_id: 用户ID
        limit: 限制

    Returns:
        思维导图列表
    """
    return app.document_store.find_mindmaps_by_user(user_id, limit)

# 危险操作！
# 仅供管理员使用
def delete_collection(app, collection_name: str) -> Dict[str, Any]:
    """删除集合

    Args:
        app: Flask应用
        collection_name: 集合名称

    Returns:
        操作结果
    """
    return app.document_store.delete_collection(collection_name)

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
    return app.document_store.upsert_user_mindmap_status(user_id, mindmap_status)

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
    return app.document_store.set_favorites(user_id, favorites)

def get_favorites(app, user_id: str) -> Dict[str, Any]:
    """获取用户收藏

    Args:
        app: Flask应用
        user_id: 用户ID

    Returns:
        收藏列表
    """
    return app.document_store.get_favorites(user_id)