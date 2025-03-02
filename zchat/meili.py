import meilisearch

from zchat.models import *

def init_app(app):
    host = app.config['MEILISEARCH_HOST']
    key = app.config['MEILISEARCH_KEY']

    app.meili_client = meilisearch.Client(host, key)
    create_indexes_to_meili(app)

def create_index_if_not_exists(app, index_name, pk_name):
    exists = False
    for index in app.meili_client.get_indexes()['results']:
        if index.uid == index_name:
            exists = True
    if not exists:
        return app.meili_client.create_index(index_name, {'primaryKey': pk_name})
    return

def create_indexes_to_meili(app):
    create_index_if_not_exists(app, 'experts', 'user_id')
    create_index_if_not_exists(app, 'newbies', 'user_id')
    create_mindmaps_index(app)
    return

def add_expert_to_meili(app, expert):
    return app.meili_client.index('experts').add_documents([expert.to_dict()])

def update_expert_to_meili(app, expert):
    return app.meili_client.index('experts').update_documents([expert.to_dict()])

def add_newbie_to_meili(app, newbie):
    return app.meili_client.index('newbies').add_documents([newbie.to_dict()])

def update_newbie_to_meili(app, newbie):
    return app.meili_client.index('newbies').update_documents([newbie.to_dict()])

def find_experts_from_meili_for(app, newbie):
    result_ids = set()
    result = []
    full_hits = app.meili_client.index('experts').search(
        f'{newbie.target_company} {newbie.target_business} {newbie.target_profession} {newbie.target_title}',
        { 'limit': 40 })

    business_hits = app.meili_client.index('experts').search(
        f'{newbie.target_business} {newbie.target_profession} {newbie.target_title}',
        { 'limit': 30 })

    profession_hits = app.meili_client.index('experts').search(
        f'{newbie.target_profession} {newbie.target_title}',
        { 'limit': 20 })

    title_hits = app.meili_client.index('experts').search(
        f'{newbie.target_title}',
        { 'limit': 10 })

    for hits in [full_hits, business_hits, profession_hits, title_hits]:
        for hit in hits['hits']:
            if hit['user_id'] in result_ids or hit['user_id'] == newbie.user_id:
                continue
            result_ids.add(hit['user_id'])
            result.append(hit)

    app.logger.debug(f"find_experts_from_meili_for, result: {len(result)}")

    return list(result)

def find_newbies_from_meili_for(app, expert):
    result_ids = set()
    result = []

    full_hits = app.meili_client.index('newbies').search(
        f'{expert.company} {expert.business} {expert.profession} {expert.title}',
        {
            'limit': 40,
            # 'matchingStrategy': 'frequency', TODO change to frequency
        })

    business_hits = app.meili_client.index('newbies').search(
        f'{expert.business} {expert.profession} {expert.title}',
        { 'limit': 30 })

    profession_hits = app.meili_client.index('newbies').search(
        f'{expert.profession} {expert.title}',
        { 'limit': 20 })

    title_hits = app.meili_client.index('newbies').search(
        f'{expert.title}',
        { 'limit': 10 })


    for hits in [full_hits, business_hits, profession_hits, title_hits]:
        for hit in hits['hits']:
            if hit['user_id'] in result_ids or hit['user_id'] == expert.user_id:
                continue
            result_ids.add(hit['user_id'])
            result.append(hit)

    return list(result)


def create_mindmaps_index(app):
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
