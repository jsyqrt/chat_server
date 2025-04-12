// 在admin数据库中进行认证
db = db.getSiblingDB('admin');
db.auth('zchat', 'zchat_password');

// 创建和初始化zchat数据库
db = db.getSiblingDB('zchat');

// 创建文档集合
if (!db.getCollectionNames().includes('documents')) {
    db.createCollection('documents');
    print("Created 'documents' collection");
}

// 检查并删除可能存在的文本索引以避免冲突
var indexes = db.documents.getIndexes();
for (var i = 0; i < indexes.length; i++) {
    var idx = indexes[i];
    if (idx.key && idx.key._fts) {
        print("Dropping existing text index: " + idx.name);
        db.documents.dropIndex(idx.name);
    }
}

// 为documents集合创建索引
db.documents.createIndex({ "id": 1 }, { unique: true });
db.documents.createIndex({ "content": "text", "metadata.title": "text" });
db.documents.createIndex({ "type": 1 });
db.documents.createIndex({ "created_at": 1 });
db.documents.createIndex({ "updated_at": 1 });
db.documents.createIndex({ "metadata.user_id": 1 });

print("Initialized MongoDB database and collections successfully");