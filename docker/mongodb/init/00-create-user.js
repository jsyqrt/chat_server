// MongoDB 初始化脚本
// 创建应用程序使用的数据库和用户

// 切换到管理员数据库
db = db.getSiblingDB('admin');

// 检查zchat用户是否已存在，如果不存在则创建
const zchatAdminUser = db.getUser('zchat');
if (!zchatAdminUser) {
    print('创建管理员用户: zchat');
    db.createUser({
        user: 'zchat',
        pwd: 'zchat_password',
        roles: [
            { role: 'userAdminAnyDatabase', db: 'admin' },
            { role: 'dbAdminAnyDatabase', db: 'admin' },
            { role: 'readWriteAnyDatabase', db: 'admin' }
        ]
    });
}

// 切换到zchat数据库
db = db.getSiblingDB('zchat');

// 创建collections集合，用于跟踪所有集合
if (!db.getCollectionNames().includes('collections')) {
    print('创建collections集合');
    db.createCollection('collections');

    // 在collections集合上创建唯一索引，确保集合名称唯一
    db.collections.createIndex({ name: 1 }, { unique: true });

    print('collections集合创建完成');
}

// 创建应用可能需要的初始数据集合
const initialCollections = [
    {
        name: 'mindmaps',
        primaryKey: 'id',
        indexedFields: ['id', 'title', 'created_by', 'difficulty'],
        options: {
            description: '思维导图集合'
        }
    },
    {
        name: 'favorites',
        primaryKey: 'user_id',
        indexedFields: ['user_id'],
        options: {
            description: '用户收藏集合'
        }
    },
    {
        name: 'file_records',
        primaryKey: 'id',
        indexedFields: ['id', 'user_id', 'filename'],
        options: {
            description: '文件记录集合'
        }
    },
    {
        name: 'feedback',
        primaryKey: 'id',
        indexedFields: ['id', 'user_id', 'status', 'created_at'],
        options: {
            description: '用户反馈集合'
        }
    }
];

// 创建初始集合
initialCollections.forEach(collInfo => {
    // 首先检查collection元数据是否已存在
    const existing = db.collections.findOne({ name: collInfo.name });
    if (!existing) {
        print(`创建${collInfo.name}集合的元数据`);

        // 添加元数据
        db.collections.insertOne({
            name: collInfo.name,
            primary_key: collInfo.primaryKey,
            created_at: new Date().getTime() / 1000,
            indexed_fields: collInfo.indexedFields,
            options: collInfo.options
        });

        // 确保集合存在
        if (!db.getCollectionNames().includes(collInfo.name)) {
            print(`创建${collInfo.name}集合`);
            db.createCollection(collInfo.name);
        }

        // 创建索引
        print(`为${collInfo.name}创建索引`);
        // 主键索引
        db[collInfo.name].createIndex({ [collInfo.primaryKey]: 1 }, { unique: true });

        // 其他索引
        collInfo.indexedFields.forEach(field => {
            if (field !== collInfo.primaryKey) {
                db[collInfo.name].createIndex({ [field]: 1 });
            }
        });

        // 添加时间索引
        db[collInfo.name].createIndex({ 'updated_at': -1 });

        print(`${collInfo.name}集合初始化完成`);
    } else {
        print(`${collInfo.name}集合元数据已存在，跳过`);
    }
});

print('MongoDB初始化脚本执行完成');