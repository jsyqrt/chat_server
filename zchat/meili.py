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

    exists = False
    for index in indexes['results']:
        if index.uid == 'newbies':
            exists = True
    if not exists:
        create_newbie_result = app.meili_client.create_index('newbies', {'primaryKey': 'user_id'})
        app.logger.debug(f"create_indexes_to_meili, create_newbie_result: {create_newbie_result}")

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
