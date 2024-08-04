import meilisearch

from zchat.models import *

def init_app(app):
    host = app.config['MEILISEARCH_HOST']
    key = app.config['MEILISEARCH_KEY']

    app.meili_client = meilisearch.Client(host, key)
    create_indexes_to_meili(app)

def create_indexes_to_meili(app):
    indexes = app.meili_client.get_indexes()
    exists = False
    for index in indexes['results']:
        if index.uid == 'experts':
            exists = True
    if not exists:
        create_expert_result = app.meili_client.create_index('experts', {'primaryKey': 'user_id'})
        app.logger.debug(f"create_indexes_to_meili, create_expert_result: {create_expert_result}")
    return

def add_expert_to_meili(app, expert):
    return app.meili_client.index('experts').add_documents([expert.to_dict()])

def update_expert_to_meili(app, expert):
    return app.meili_client.index('experts').update_documents([expert.to_dict()])

def find_experts_from_meili_for(app, newbie):
    per_limit = 10
    result_ids = set()
    result = []
    company_hits = app.meili_client.index('experts').search(f'{newbie.target_company}', {
        'limit': per_limit
    })

    title_hits = app.meili_client.index('experts').search(f'{newbie.target_title}', {
        'limit': per_limit
    })

    profession_hits = app.meili_client.index('experts').search(f'{newbie.target_profession}', {
        'limit': per_limit
    })

    business_hits = app.meili_client.index('experts').search(f'{newbie.target_business}', {
        'limit': per_limit
    })

    for hits in [company_hits, title_hits, profession_hits, business_hits]:
        for hit in hits['hits']:
            if hit['user_id'] in result_ids or hit['user_id'] == newbie.user_id:
                continue
            result_ids.add(hit['user_id'])
            result.append(hit)

    return list(result)