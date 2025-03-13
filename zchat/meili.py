import meilisearch

def init_app(app):
    host = app.config['MEILISEARCH_HOST']
    key = app.config['MEILISEARCH_KEY']

    app.meili_client = meilisearch.Client(host, key)
    create_indexes_to_meili(app)

def create_indexes_to_meili(app):
    create_mindmaps_index(app)
    return

# --- mindmaps ---

def create_mindmaps_index(app):
    exists = False
    for index in app.meili_client.get_indexes()['results']:
        if index.uid == 'mindmaps':
            exists = True
    if not exists:
        app.meili_client.create_index( 'mindmaps', { 'primaryKey': 'id' })
        app.meili_client.index('mindmaps').update_settings({
            'searchableAttributes': [
                'title',
                'description',
            ],
            'filterableAttributes': [
                'title',
                'created_by',
                'roadmap_id',
            ],
            'sortableAttributes': [
                'created_at',
                'updated_at'
            ]
        })
    return

def add_mindmap_to_meili(app, mindmap):
    return app.meili_client.index('mindmaps').add_documents([mindmap])

def update_mindmap_to_meili(app, mindmap):
    return app.meili_client.index('mindmaps').update_documents([mindmap])

def get_mindmap_from_meili(app, mindmap_id):
    doc = app.meili_client.index('mindmaps').get_document(mindmap_id)
    result = {}
    for key, value in doc:
        result[key] = value
    return result

def get_mindmap_from_meili_by_roadmap_id(app, roadmap_id):
    result = {}
    hits = app.meili_client.index('mindmaps').search('', { 'filter': [f'roadmap_id={roadmap_id}'] })
    for hit in hits['hits']:
        result = hit
        break
    return result

def search_mindmaps_from_meili_for(app, topic, offset=0, limit=10):
    result = []
    hits = app.meili_client.index('mindmaps').search(topic, { 'offset': offset, 'limit': limit, 'sort': ['updated_at:desc'] })
    for hit in hits['hits']:
        result.append(hit)
    return result

def find_mindmaps_from_meili_created_by(app, user_id):
    result = []
    hits = app.meili_client.index('mindmaps').search('', { 'filter': [f'created_by={user_id}'] })
    for hit in hits['hits']:
        result.append(hit)
    return result

def delete_mindmap_from_meili(app, mindmap_id):
    return app.meili_client.index('mindmaps').delete_document(mindmap_id)

# --- user mindmap status ---

def create_user_mindmap_status_index(app, user_id):
    exists = False
    index_name = f'user_mindmap_status_{user_id}'

    for index in app.meili_client.get_indexes()['results']:
        if index.uid == index_name:
            exists = True
    if not exists:
        app.meili_client.create_index(index_name, { 'primaryKey': 'mindmap_id' })
        app.meili_client.index(index_name).update_settings({
            'filterableAttributes': [
                'mindmap_id',
                'learning_status', # todo, doing, done
            ],
            'sortableAttributes': [
                'created_at',
                'updated_at'
            ]
        })
    return

def add_user_mindmap_status_to_meili(app, user_id, mindmap_status):
    create_user_mindmap_status_index(app, user_id)
    return app.meili_client.index(f'user_mindmap_status_{user_id}').add_documents([mindmap_status])

def update_user_mindmap_status_to_meili(app, user_id, mindmap_status):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').update_documents([mindmap_status])

def get_learning_status_from_meili(app, user_id, mindmap_id):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').search('', { 'filter': [f'mindmap_id={mindmap_id}'] })

def get_learning_list_from_meili(app, user_id, offset=0, limit=3):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').search('', { 'offset': offset, 'limit': limit, 'sort': ['updated_at:desc'] })['hits']

# DANGER!
# only for admin
def delete_index_from_meili(app, index_name):
    return app.meili_client.delete_index(index_name)
