import meilisearch

def init_app(app):
    host = app.config['MEILISEARCH_HOST']
    key = app.config['MEILISEARCH_KEY']

    app.meili_client = meilisearch.Client(host, key)
    create_indexes_to_meili(app)

def create_indexes_to_meili(app):
    create_user_mindmaps_index(app)
    return

def create_user_mindmaps_index(app):
    exists = False
    for index in app.meili_client.get_indexes()['results']:
        if index.uid == 'user_mindmaps':
            exists = True
    if not exists:
        app.meili_client.create_index( 'user_mindmaps', { 'primaryKey': 'uuid' })
        app.meili_client.index('user_mindmaps').update_settings({
            'searchableAttributes': [
                'mindmap_title',
            ],
            'filterableAttributes': [
                'mindmap_title',
                'mindmap_type',
                'mindmap_kind',
                'created_by'
            ],
            'sortableAttributes': [
                'created_at',
                'updated_at'
            ]
        })
    return

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
        })
    return

def add_user_mindmap_to_meili(app, mindmap):
    return app.meili_client.index('user_mindmaps').add_documents([mindmap])

def update_user_mindmap_to_meili(app, mindmap):
    return app.meili_client.index('user_mindmaps').update_documents([mindmap])

def find_mindmaps_from_meili_for(app, topic):
    result = []
    hits = app.meili_client.index('user_mindmaps').search('', { 'limit': 10, 'filter': [f'mindmap_title={topic}'] })
    for hit in hits['hits']:
        result.append(hit)
    return result

def find_user_mindmaps_from_meili_created_by(app, user_id):
    result = []
    hits = app.meili_client.index('user_mindmaps').search('', { 'filter': [f'created_by={user_id}'] })
    for hit in hits['hits']:
        result.append(hit)
    return result

def add_user_mindmap_status_to_meili(app, user_id, mindmap_status):
    create_user_mindmap_status_index(app, user_id)
    return app.meili_client.index(f'user_mindmap_status_{user_id}').add_documents([mindmap_status])

def update_user_mindmap_status_to_meili(app, user_id, mindmap_status):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').update_documents([mindmap_status])

def find_user_mindmap_status_from_meili(app, user_id, mindmap_id):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').search('', { 'filter': [f'mindmap_id={mindmap_id}'] })

def list_all_user_mindmap_status_from_meili(app, user_id):
    return app.meili_client.index(f'user_mindmap_status_{user_id}').get_documents().results
