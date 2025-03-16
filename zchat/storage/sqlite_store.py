import json
import time
import sqlite3
import os
import threading
from typing import Dict, List, Any, Optional, Union
from .abstract import DocumentStore

class SQLiteDocumentStore(DocumentStore):
    """基于SQLite的文档存储实现，针对KV存储场景优化"""

    def __init__(self, db_path: str):
        """初始化SQLite存储

        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.local = threading.local()  # 使用线程本地存储
        self.lock = threading.RLock()   # 使用可重入锁
        self._init_db()

    def _get_connection(self):
        """获取线程安全的数据库连接"""
        if not hasattr(self.local, 'conn') or self.local.conn is None:
            self.local.conn = sqlite3.connect(self.db_path)
            self.local.conn.row_factory = sqlite3.Row
            # 启用外键约束
            self.local.conn.execute("PRAGMA foreign_keys = ON")
            # 启用WAL模式以提高并发性能
            self.local.conn.execute("PRAGMA journal_mode = WAL")
            # 设置同步模式以提高写入性能
            self.local.conn.execute("PRAGMA synchronous = NORMAL")
            # 设置缓存大小
            self.local.conn.execute("PRAGMA cache_size = 10000")
            # 设置页大小
            self.local.conn.execute("PRAGMA page_size = 8192")
            # 设置临时存储在内存中
            self.local.conn.execute("PRAGMA temp_store = MEMORY")
        return self.local.conn

    def _init_db(self):
        """初始化数据库架构"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # 创建集合表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                name TEXT PRIMARY KEY,
                primary_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                options TEXT
            )
            ''')
            conn.commit()

            # 创建文档表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                collection_name TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (collection_name, doc_id),
                FOREIGN KEY (collection_name) REFERENCES collections(name) ON DELETE CASCADE
            )
            ''')

            # 创建索引字段表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indexed_fields (
                collection_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                PRIMARY KEY (collection_name, field_name),
                FOREIGN KEY (collection_name) REFERENCES collections(name) ON DELETE CASCADE
            )
            ''')

            # 创建索引值表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS field_values (
                collection_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_value TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                PRIMARY KEY (collection_name, field_name, field_value, doc_id),
                FOREIGN KEY (collection_name, doc_id) REFERENCES documents(collection_name, doc_id) ON DELETE CASCADE,
                FOREIGN KEY (collection_name, field_name) REFERENCES indexed_fields(collection_name, field_name) ON DELETE CASCADE
            )
            ''')

            # 创建索引以加快查询
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents (updated_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_field_values_value ON field_values (field_value)')

            conn.commit()

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建一个新的集合

        Args:
            collection_name: 集合名称
            options: 集合选项，可以包含 primaryKey 和 indexedFields

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()

        if options is None:
            options = {}

        primary_key = options.get('primaryKey', 'id')
        indexed_fields = options.get('indexedFields', [])

        with self.lock:
            try:
                cursor = conn.cursor()

                # 检查集合是否已存在
                cursor.execute('SELECT name FROM collections WHERE name = ?', (collection_name,))
                if cursor.fetchone():
                    return {"status": "error", "message": f"Collection {collection_name} already exists"}

                # 创建集合
                now = time.time()
                cursor.execute(
                    'INSERT INTO collections (name, primary_key, created_at, options) VALUES (?, ?, ?, ?)',
                    (collection_name, primary_key, now, json.dumps(options))
                )

                # 添加索引字段
                for field in indexed_fields:
                    cursor.execute(
                        'INSERT INTO indexed_fields (collection_name, field_name) VALUES (?, ?)',
                        (collection_name, field)
                    )

                # 始终为主键添加索引
                cursor.execute(
                    'INSERT OR IGNORE INTO indexed_fields (collection_name, field_name) VALUES (?, ?)',
                    (collection_name, primary_key)
                )

                conn.commit()

                return {"status": "success", "collectionName": collection_name}
            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除一个集合及其所有文档

        Args:
            collection_name: 集合名称

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()

        with self.lock:
            try:
                cursor = conn.cursor()

                # 检查集合是否存在
                cursor.execute('SELECT name FROM collections WHERE name = ?', (collection_name,))
                if not cursor.fetchone():
                    return {"status": "error", "message": f"Collection {collection_name} does not exist"}

                # 删除集合（级联删除会自动删除相关的文档和索引）
                cursor.execute('DELETE FROM collections WHERE name = ?', (collection_name,))

                conn.commit()

                return {"status": "success", "message": f"Collection {collection_name} deleted"}
            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            包含集合列表的字典
        """
        conn = self._get_connection()

        with self.lock:
            cursor = conn.cursor()

            cursor.execute('SELECT name, primary_key, created_at, options FROM collections')

            collections = []
            for row in cursor.fetchall():
                options = json.loads(row['options']) if row['options'] else {}
                collections.append({
                    'name': row['name'],
                    'primaryKey': row['primary_key'],
                    'createdAt': row['created_at'],
                    'options': options
                })

            return {"collections": collections}

    def _get_collection_primary_key(self, collection_name: str) -> Optional[str]:
        """获取集合的主键

        Args:
            collection_name: 集合名称

        Returns:
            主键名称，如果集合不存在则为None
        """
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()
            cursor.execute('SELECT primary_key FROM collections WHERE name = ?', (collection_name,))
            row = cursor.fetchone()

            if row is None:
                return None

            return row['primary_key']

    def _get_indexed_fields(self, collection_name: str) -> List[str]:
        """获取集合的索引字段

        Args:
            collection_name: 集合名称

        Returns:
            索引字段列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT field_name FROM indexed_fields WHERE collection_name = ?',
            (collection_name,)
        )

        return [row['field_name'] for row in cursor.fetchall()]

    def add_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """向集合中添加文档

        Args:
            collection_name: 集合名称
            document: 要添加的文档

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            # 如果集合不存在，则创建它
            self.create_collection(collection_name)
            primary_key = 'id'  # 默认主键

        # 确保文档有主键
        if primary_key not in document:
            return {"status": "error", "message": f"Document must have primary key {primary_key}"}

        doc_id = str(document[primary_key])

        # 准备文档
        now = time.time()
        doc_with_timestamps = document.copy()
        if 'created_at' not in doc_with_timestamps:
            doc_with_timestamps['created_at'] = now
        if 'updated_at' not in doc_with_timestamps:
            doc_with_timestamps['updated_at'] = now

        # 将文档转换为JSON
        doc_json = json.dumps(doc_with_timestamps)

        with self.lock:
            try:
                cursor = conn.cursor()

                # 插入文档
                cursor.execute(
                    'INSERT INTO documents (collection_name, doc_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                    (collection_name, doc_id, doc_json, now, now)
                )

                # 更新索引
                self._update_field_values(cursor, collection_name, doc_id, doc_with_timestamps)

                conn.commit()

                return {"status": "success", "documentId": doc_id}
            except sqlite3.IntegrityError:
                conn.rollback()
                return {"status": "error", "message": f"Document with id {doc_id} already exists"}
            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}

    def update_document(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """更新集合中的文档

        Args:
            collection_name: 集合名称
            document: 要更新的文档

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()

        # 获取集合的主键
        primary_key = self._get_collection_primary_key(collection_name)
        if not primary_key:
            return {"status": "error", "message": f"Collection {collection_name} does not exist"}

        # 确保文档有主键
        if primary_key not in document:
            return {"status": "error", "message": f"Document must have primary key {primary_key}"}

        doc_id = str(document[primary_key])

        with self.lock:
            try:
                cursor = conn.cursor()

                # 检查文档是否存在
                cursor.execute(
                    'SELECT doc_id FROM documents WHERE collection_name = ? AND doc_id = ?',
                    (collection_name, doc_id)
                )
                if cursor.fetchone() is None:
                    return self.add_document(collection_name, document)

                # 获取现有文档
                cursor.execute(
                    'SELECT content FROM documents WHERE collection_name = ? AND doc_id = ?',
                    (collection_name, doc_id)
                )
                row = cursor.fetchone()
                existing_doc = json.loads(row['content'])

                # 合并文档
                merged_doc = {**existing_doc, **document}

                # 更新时间戳
                now = time.time()
                merged_doc['updated_at'] = now

                # 将文档转换为JSON
                doc_json = json.dumps(merged_doc)

                # 更新文档
                cursor.execute(
                    '''
                    UPDATE documents
                    SET content = ?, updated_at = ?
                    WHERE collection_name = ? AND doc_id = ?
                    ''',
                    (doc_json, now, collection_name, doc_id)
                )

                # 更新索引
                self._update_field_values(cursor, collection_name, doc_id, merged_doc)

                conn.commit()

                return {"status": "success", "documentId": doc_id}
            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            文档，如果不存在则为None
        """
        conn = self._get_connection()

        with self.lock:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT content FROM documents WHERE collection_name = ? AND doc_id = ?',
                (collection_name, doc_id)
            )

            row = cursor.fetchone()
            if row is None:
                return None

            return json.loads(row['content'])

    def delete_document(self, collection_name: str, doc_id: str) -> Dict[str, Any]:
        """删除文档

        Args:
            collection_name: 集合名称
            doc_id: 文档ID

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()

        with self.lock:
            try:
                cursor = conn.cursor()

                # 检查文档是否存在
                cursor.execute(
                    'SELECT doc_id FROM documents WHERE collection_name = ? AND doc_id = ?',
                    (collection_name, doc_id)
                )
                if cursor.fetchone() is None:
                    return {"status": "error", "message": f"Document with id {doc_id} does not exist"}

                # 删除文档（级联删除会自动删除相关的索引值）
                cursor.execute(
                    'DELETE FROM documents WHERE collection_name = ? AND doc_id = ?',
                    (collection_name, doc_id)
                )

                conn.commit()

                return {"status": "success", "message": f"Document with id {doc_id} deleted"}
            except Exception as e:
                conn.rollback()
                return {"status": "error", "message": str(e)}

    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档

        Args:
            collection_name: 集合名称
            query: 搜索查询
            options: 搜索选项，可以包含 filter, sort, limit, offset

        Returns:
            包含搜索结果的字典
        """
        conn = self._get_connection()

        if options is None:
            options = {}

        filters = options.get('filter', [])
        sort = options.get('sort', [])
        limit = options.get('limit', 20)
        offset = options.get('offset', 0)

        with self.lock:
            cursor = conn.cursor()

            # 构建查询
            sql = 'SELECT DISTINCT d.content FROM documents d'
            params = []

            # 处理过滤器
            filter_conditions = []
            if filters:
                for i, filter_expr in enumerate(filters):
                    # 支持多种过滤器格式: field=value, field:value, field=value1,value2
                    if '=' in filter_expr:
                        field, value = filter_expr.split('=', 1)
                    elif ':' in filter_expr:
                        field, value = filter_expr.split(':', 1)
                    else:
                        continue  # 跳过无效的过滤器

                    field = field.strip()
                    value = value.strip()

                    # 检查字段是否是索引字段
                    cursor.execute(
                        'SELECT field_name FROM indexed_fields WHERE collection_name = ? AND field_name = ?',
                        (collection_name, field)
                    )
                    if not cursor.fetchone():
                        # 如果不是索引字段，使用 JSON 提取
                        filter_conditions.append(f'json_extract(d.content, "$.{field}") = ?')
                        params.append(value)
                    else:
                        # 如果是索引字段，使用索引表
                        sql += f' JOIN field_values fv{i} ON d.collection_name = fv{i}.collection_name AND d.doc_id = fv{i}.doc_id'
                        filter_conditions.append(f'fv{i}.field_name = ? AND fv{i}.field_value = ?')
                        params.extend([field, value])

            # 添加基本条件
            filter_conditions.append('d.collection_name = ?')
            params.append(collection_name)

            # 处理查询
            if query:
                # 简单的模糊匹配
                filter_conditions.append('d.content LIKE ?')
                params.append(f'%{query}%')

            # 添加 WHERE 子句
            if filter_conditions:
                sql += ' WHERE ' + ' AND '.join(filter_conditions)

            # 处理排序
            if sort:
                order_clauses = []
                for sort_expr in sort:
                    field, direction = sort_expr.split(':') if ':' in sort_expr else (sort_expr, 'asc')
                    order_clauses.append(f'json_extract(d.content, "$.{field}") {"DESC" if direction.lower() == "desc" else "ASC"}')

                if order_clauses:
                    sql += ' ORDER BY ' + ', '.join(order_clauses)

            # 添加分页
            sql += ' LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            # 执行查询
            try:
                cursor.execute(sql, params)
            except sqlite3.Error as e:
                # 记录错误并返回空结果
                print(f"SQLite error: {e}")
                print(f"SQL: {sql}")
                print(f"Params: {params}")
                return {
                    "hits": [],
                    "offset": offset,
                    "limit": limit,
                    "estimatedTotalHits": 0,
                    "query": query,
                    "processingTimeMs": 0,
                    "error": str(e)
                }

            # 处理结果
            hits = []
            for row in cursor.fetchall():
                hits.append(json.loads(row['content']))

            # 获取总数
            count_sql = 'SELECT COUNT(DISTINCT d.doc_id) as count FROM documents d'
            count_params = []

            # 处理过滤器
            count_filter_conditions = []
            if filters:
                for i, filter_expr in enumerate(filters):
                    # 支持多种过滤器格式
                    if '=' in filter_expr:
                        field, value = filter_expr.split('=', 1)
                    elif ':' in filter_expr:
                        field, value = filter_expr.split(':', 1)
                    else:
                        continue

                    field = field.strip()
                    value = value.strip()

                    # 检查字段是否是索引字段
                    cursor.execute(
                        'SELECT field_name FROM indexed_fields WHERE collection_name = ? AND field_name = ?',
                        (collection_name, field)
                    )
                    if not cursor.fetchone():
                        # 如果不是索引字段，使用 JSON 提取
                        count_filter_conditions.append(f'json_extract(d.content, "$.{field}") = ?')
                        count_params.append(value)
                    else:
                        # 如果是索引字段，使用索引表
                        count_sql += f' JOIN field_values fv{i} ON d.collection_name = fv{i}.collection_name AND d.doc_id = fv{i}.doc_id'
                        count_filter_conditions.append(f'fv{i}.field_name = ? AND fv{i}.field_value = ?')
                        count_params.extend([field, value])

            # 添加基本条件
            count_filter_conditions.append('d.collection_name = ?')
            count_params.append(collection_name)

            # 处理查询
            if query:
                count_filter_conditions.append('d.content LIKE ?')
                count_params.append(f'%{query}%')

            # 添加 WHERE 子句
            if count_filter_conditions:
                count_sql += ' WHERE ' + ' AND '.join(count_filter_conditions)

            try:
                cursor.execute(count_sql, count_params)
                count = cursor.fetchone()['count']
            except sqlite3.Error as e:
                # 记录错误并使用 hits 长度作为总数
                print(f"SQLite count error: {e}")
                print(f"SQL: {count_sql}")
                print(f"Params: {count_params}")
                count = len(hits)

            return {
                "hits": hits,
                "offset": offset,
                "limit": limit,
                "estimatedTotalHits": count,
                "query": query,
                "processingTimeMs": 0  # 不计算处理时间
            }

    def _update_field_values(self, cursor, collection_name: str, doc_id: str, document: Dict[str, Any]):
        """更新文档的索引字段值

        Args:
            cursor: 数据库游标
            collection_name: 集合名称
            doc_id: 文档ID
            document: 文档内容
        """
        # 获取索引字段
        cursor.execute(
            'SELECT field_name FROM indexed_fields WHERE collection_name = ?',
            (collection_name,)
        )
        indexed_fields = [row['field_name'] for row in cursor.fetchall()]

        # 删除现有的索引值
        cursor.execute(
            'DELETE FROM field_values WHERE collection_name = ? AND doc_id = ?',
            (collection_name, doc_id)
        )

        # 添加新的索引值
        for field in indexed_fields:
            value = self._get_field_value(document, field)
            if value is not None:
                # 确保值是字符串
                str_value = str(value)
                cursor.execute(
                    'INSERT INTO field_values (collection_name, field_name, field_value, doc_id) VALUES (?, ?, ?, ?)',
                    (collection_name, field, str_value, doc_id)
                )

    def _get_field_value(self, doc: Dict[str, Any], field: str) -> Any:
        """获取文档中字段的值

        Args:
            doc: 文档对象
            field: 字段名

        Returns:
            字段值
        """
        # 处理带点符号的嵌套字段
        if '.' in field:
            parts = field.split('.')
            current = doc
            for part in parts:
                if part in current:
                    current = current[part]
                else:
                    return None
            return current
        else:
            return doc.get(field)

    def close(self):
        """关闭数据库连接"""
        if hasattr(self.local, 'conn') and self.local.conn is not None:
            self.local.conn.close()
            self.local.conn = None