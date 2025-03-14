# This file now serves as a compatibility layer that redirects to storage.api
from zchat.storage.api import (
    init_app,
    create_initial_collections as create_indexes_to_meili,
    create_mindmaps_collection as create_mindmaps_index,
    add_mindmap as add_mindmap_to_meili,
    update_mindmap as update_mindmap_to_meili,
    get_mindmap as get_mindmap_from_meili,
    delete_mindmap as delete_mindmap_from_meili,
    create_user_mindmap_status_collection,
    add_user_mindmap_status as add_user_mindmap_status_to_meili,
    update_user_mindmap_status as update_user_mindmap_status_to_meili,
    upsert_user_mindmap_status as upsert_user_mindmap_status_to_meili,
    get_learning_status as get_learning_status_from_meili,
    get_learning_list as get_learning_list_from_meili,
    delete_collection as delete_index_from_meili,
    find_mindmaps_for as find_mindmaps_from_meili_for,
    find_user_mindmaps_created_by as find_user_mindmaps_from_meili_created_by
)
