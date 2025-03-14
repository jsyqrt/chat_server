import os
from zchat.sqlite_store import SQLiteStore

# Global store instance
_store = None

def init_app(app):
    """Initialize the SQLite store"""
    global _store

    # Configure the SQLite path
    db_path = app.config.get('SQLITE_PATH', os.path.join(app.instance_path, 'sqlite_store.db'))

    # Create the store
    _store = SQLiteStore(db_path)
    app.sqlite_store = _store

    # Create initial indexes
    create_indexes_to_sqlite(app)

def create_indexes_to_sqlite(app):
    """Create initial indexes"""
    create_mindmaps_index(app)
    return

# --- mindmaps ---

def create_mindmaps_index(app):
    """Create the mindmaps index if it doesn't exist"""
    exists = False
    for index in app.sqlite_store.get_indexes()['results']:
        if index['uid'] == 'mindmaps':
            exists = True
    if not exists:
        app.sqlite_store.create_index('mindmaps', {'primaryKey': 'id'})
    return

def add_mindmap_to_sqlite(app, mindmap):
    """Add a mindmap to the store"""
    return app.sqlite_store.add_document('mindmaps', mindmap)

def update_mindmap_to_sqlite(app, mindmap):
    """Update a mindmap in the store"""
    return app.sqlite_store.update_document('mindmaps', mindmap)

def get_mindmap_from_sqlite(app, mindmap_id):
    """Get a mindmap from the store"""
    doc = app.sqlite_store.get_document('mindmaps', mindmap_id)
    if doc:
        return doc
    return {}

def delete_mindmap_from_sqlite(app, mindmap_id):
    """Delete a mindmap from the store"""
    return app.sqlite_store.delete_document('mindmaps', mindmap_id)

# --- user mindmap status ---

def create_user_mindmap_status_index(app, user_id):
    """Create a user mindmap status index if it doesn't exist"""
    index_name = f'user_mindmap_status_{user_id}'

    exists = False
    for index in app.sqlite_store.get_indexes()['results']:
        if index['uid'] == index_name:
            exists = True
    if not exists:
        app.sqlite_store.create_index(index_name, {'primaryKey': 'mindmap_id'})
    return

def add_user_mindmap_status_to_sqlite(app, user_id, mindmap_status):
    """Add a user mindmap status to the store"""
    create_user_mindmap_status_index(app, user_id)
    return app.sqlite_store.add_document(f'user_mindmap_status_{user_id}', mindmap_status)

def update_user_mindmap_status_to_sqlite(app, user_id, mindmap_status):
    """Update a user mindmap status in the store"""
    return app.sqlite_store.update_document(f'user_mindmap_status_{user_id}', mindmap_status)

def get_learning_status_from_sqlite(app, user_id, mindmap_id):
    """Get a learning status from the store"""
    return app.sqlite_store.search(f'user_mindmap_status_{user_id}', '', {'filter': [f'mindmap_id={mindmap_id}']})

def get_learning_list_from_sqlite(app, user_id, offset=0, limit=3):
    """Get a learning list from the store"""
    return app.sqlite_store.search(f'user_mindmap_status_{user_id}', '', {'offset': offset, 'limit': limit, 'sort': ['updated_at:desc']})['hits']

# Search functions
def find_mindmaps_from_sqlite_for(app, topic, limit=10):
    """Find mindmaps matching a topic"""
    return app.sqlite_store.search('mindmaps', topic, {'limit': limit})['hits']

def find_user_mindmaps_from_sqlite_created_by(app, user_id, limit=10):
    """Find mindmaps created by a user"""
    return app.sqlite_store.search('mindmaps', '', {'filter': [f'created_by={user_id}'], 'limit': limit})['hits']

# DANGER!
# only for admin
def delete_index_from_sqlite(app, index_name):
    """Delete an index from the store"""
    return app.sqlite_store.delete_index(index_name)