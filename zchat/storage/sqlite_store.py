import json
import time
import sqlite3
import os
import threading
from typing import Dict, List, Any, Optional, Union
from .abstract import DocumentStore

class SQLiteDocumentStore(DocumentStore):
    """基于SQLite的文档存储实现，使用JSON1扩展提高性能"""

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

            # 创建搜索词表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_terms (
                collection_name TEXT NOT NULL,
                term TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                PRIMARY KEY (collection_name, term, doc_id),
                FOREIGN KEY (collection_name, doc_id) REFERENCES documents(collection_name, doc_id) ON DELETE CASCADE
            )
            ''')

            # 创建索引以加快搜索
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_terms_term ON search_terms (term)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents (updated_at)')

            conn.commit()

    def create_collection(self, collection_name: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建一个新的集合

        Args:
            collection_name: 集合名称
            options: 集合选项，如主键字段名

        Returns:
            包含操作状态的字典
        """
        if options is None:
            options = {'primaryKey': 'id'}

        primary_key = options.get('primaryKey', 'id')
        created_at = time.time()

        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # 检查集合是否已存在
            cursor.execute('SELECT name FROM collections WHERE name = ?', (collection_name,))
            if cursor.fetchone() is None:
                cursor.execute(
                    'INSERT INTO collections (name, primary_key, created_at, options) VALUES (?, ?, ?, ?)',
                    (collection_name, primary_key, created_at, json.dumps(options))
                )
                conn.commit()

        return {"status": "success", "collectionName": collection_name}

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除一个集合及其所有文档

        Args:
            collection_name: 要删除的集合名称

        Returns:
            包含操作状态的字典
        """
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # 删除集合（级联删除会自动删除相关文档和搜索词）
            cursor.execute('DELETE FROM collections WHERE name = ?', (collection_name,))
            conn.commit()

        return {"status": "success"}

    def list_collections(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有集合

        Returns:
            包含所有集合信息的字典
        """
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()
            cursor.execute('SELECT name, primary_key, created_at, options FROM collections')

            results = []
            for row in cursor.fetchall():
                options = json.loads(row['options']) if row['options'] else {}
                results.append({
                    "name": row['name'],
                    "primaryKey": row['primary_key'],
                    "createdAt": row['created_at'],
                    "options": options
                })

        return {"collections": results}

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

                # 为文档添加搜索词
                self._add_search_terms(cursor, collection_name, doc_id, doc_with_timestamps)

                # 提交事务
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

                # 准备文档
                now = time.time()
                doc_with_timestamps = document.copy()
                if 'updated_at' not in doc_with_timestamps:
                    doc_with_timestamps['updated_at'] = now

                # 将文档转换为JSON
                doc_json = json.dumps(doc_with_timestamps)

                # 更新文档
                cursor.execute(
                    '''
                    UPDATE documents
                    SET content = ?, updated_at = ?
                    WHERE collection_name = ? AND doc_id = ?
                    ''',
                    (doc_json, now, collection_name, doc_id)
                )

                # 更新搜索词
                self._add_search_terms(cursor, collection_name, doc_id, doc_with_timestamps)

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
            文档对象，如果不存在则返回None
        """
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT content FROM documents WHERE collection_name = ? AND doc_id = ?',
                (collection_name, doc_id)
            )

            row = cursor.fetchone()
            if row:
                return json.loads(row['content'])

        return None

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
            cursor = conn.cursor()

            # 删除文档（级联删除会自动删除相关搜索词）
            cursor.execute(
                'DELETE FROM documents WHERE collection_name = ? AND doc_id = ?',
                (collection_name, doc_id)
            )

            conn.commit()

        return {"status": "success"}

    def search(self, collection_name: str, query: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """搜索文档

        Args:
            collection_name: 集合名称
            query: 搜索查询
            options: 搜索选项，如偏移量、限制、过滤器和排序

        Returns:
            包含搜索结果的字典
        """
        if options is None:
            options = {}

        offset = options.get('offset', 0)
        limit = options.get('limit', 20)
        filters = options.get('filter', [])
        sort = options.get('sort', [])

        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # 如果查询为空，获取所有文档
            if not query:
                return self._get_all_documents(cursor, collection_name, offset, limit, filters, sort)

            # 将查询拆分为词条
            query_terms = ''.join(c if c.isalnum() else ' ' for c in query).lower().split()

            # 查找匹配所有查询词条的文档
            matching_doc_ids = None
            for term in query_terms:
                cursor.execute(
                    '''
                    SELECT DISTINCT doc_id FROM search_terms
                    WHERE collection_name = ? AND term LIKE ?
                    ''',
                    (collection_name, f"%{term}%")
                )

                term_doc_ids = {row['doc_id'] for row in cursor.fetchall()}

                if matching_doc_ids is None:
                    matching_doc_ids = term_doc_ids
                else:
                    matching_doc_ids &= term_doc_ids

                if not matching_doc_ids:
                    break

            if not matching_doc_ids or len(matching_doc_ids) == 0:
                return {"hits": [], "offset": offset, "limit": limit, "estimatedTotalHits": 0}

            # 获取匹配的文档
            placeholders = ','.join(['?'] * len(matching_doc_ids))
            query_params = [collection_name] + list(matching_doc_ids)

            cursor.execute(
                f'''
                SELECT doc_id, content FROM documents
                WHERE collection_name = ? AND doc_id IN ({placeholders})
                ''',
                query_params
            )

            hits = []
            for row in cursor.fetchall():
                doc = json.loads(row['content'])
                if self._passes_filters(doc, filters):
                    hits.append(doc)

            # 应用排序
            if sort:
                hits = self._apply_sorting(hits, sort)

            # 应用分页
            total_hits = len(hits)
            hits = hits[offset:offset+limit]

            return {
                "hits": hits,
                "offset": offset,
                "limit": limit,
                "estimatedTotalHits": total_hits
            }

    def _update_search_terms(self, cursor, collection_name: str, doc_id: str, document: Dict[str, Any]):
        """更新文档的搜索词（为了向后兼容）

        Args:
            cursor: 数据库游标
            collection_name: 集合名称
            doc_id: 文档ID
            document: 文档内容
        """
        # 调用新的方法
        self._add_search_terms(cursor, collection_name, doc_id, document)

    def _extract_searchable_terms(self, document: Dict[str, Any]) -> set:
        """从文档中提取可搜索词条

        Args:
            document: 文档对象

        Returns:
            可搜索词条集合
        """
        terms = set()

        def extract_terms(obj):
            if isinstance(obj, str):
                # 按非字母数字字符拆分并转换为小写
                for term in ''.join(c if c.isalnum() else ' ' for c in obj).lower().split():
                    if term and len(term) > 1:  # 跳过单字符词条
                        terms.add(term)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_terms(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_terms(item)

        extract_terms(document)
        return terms

    def _get_all_documents(self, cursor, collection_name: str, offset: int, limit: int,
                          filters: List[str], sort: List[str]) -> Dict[str, Any]:
        """获取集合中的所有文档，带分页和过滤

        Args:
            cursor: 数据库游标
            collection_name: 集合名称
            offset: 结果偏移量
            limit: 结果限制
            filters: 过滤器列表
            sort: 排序字段列表

        Returns:
            包含文档的字典
        """
        cursor.execute(
            'SELECT content FROM documents WHERE collection_name = ? ORDER BY updated_at DESC',
            (collection_name,)
        )

        hits = []
        for row in cursor.fetchall():
            doc = json.loads(row['content'])
            if self._passes_filters(doc, filters):
                hits.append(doc)

        # 应用排序
        if sort:
            hits = self._apply_sorting(hits, sort)

        # 应用分页
        total_hits = len(hits)
        hits = hits[offset:offset+limit]

        return {
            "hits": hits,
            "offset": offset,
            "limit": limit,
            "estimatedTotalHits": total_hits
        }

    def _passes_filters(self, doc: Dict[str, Any], filters: List[str]) -> bool:
        """检查文档是否通过所有过滤器

        Args:
            doc: 文档对象
            filters: 过滤器列表

        Returns:
            如果文档通过所有过滤器，则为True
        """
        if not filters:
            return True

        for filter_str in filters:
            if not self._passes_filter(doc, filter_str):
                return False

        return True

    def _passes_filter(self, doc: Dict[str, Any], filter_str: str) -> bool:
        """检查文档是否通过单个过滤器

        Args:
            doc: 文档对象
            filter_str: 过滤器字符串

        Returns:
            如果文档通过过滤器，则为True
        """
        # 简单过滤器解析，用于等式过滤器（field=value）
        if '=' in filter_str:
            field, value = filter_str.split('=', 1)

            # 处理带点符号的嵌套字段
            if '.' in field:
                parts = field.split('.')
                current = doc
                for part in parts[:-1]:
                    if part in current:
                        current = current[part]
                    else:
                        return False
                field = parts[-1]

                if field in current and str(current[field]) == value:
                    return True
            else:
                if field in doc and str(doc[field]) == value:
                    return True

            return False

        return True

    def _apply_sorting(self, hits: List[Dict[str, Any]], sort_fields: List[str]) -> List[Dict[str, Any]]:
        """根据排序字段对结果进行排序

        Args:
            hits: 文档列表
            sort_fields: 排序字段列表

        Returns:
            排序后的文档列表
        """
        for sort_field in reversed(sort_fields):
            reverse = False
            field = sort_field

            if ':' in sort_field:
                field, direction = sort_field.split(':', 1)
                reverse = direction.lower() == 'desc'

            # 根据字段排序
            hits.sort(key=lambda doc: self._get_sort_key(doc, field), reverse=reverse)

        return hits

    def _get_sort_key(self, doc: Dict[str, Any], field: str) -> Any:
        """获取文档的排序键

        Args:
            doc: 文档对象
            field: 排序字段

        Returns:
            排序键值
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

    def _add_search_terms(self, cursor, collection_name: str, doc_id: str, document: Dict[str, Any]):
        """为文档添加搜索词

        Args:
            cursor: 数据库游标
            collection_name: 集合名称
            doc_id: 文档ID
            document: 文档内容
        """
        # 删除现有的搜索词
        cursor.execute(
            'DELETE FROM search_terms WHERE collection_name = ? AND doc_id = ?',
            (collection_name, doc_id)
        )

        # 提取搜索词
        terms = self._extract_search_terms(document)

        # 添加新的搜索词
        for term in terms:
            cursor.execute(
                'INSERT INTO search_terms (collection_name, term, doc_id) VALUES (?, ?, ?)',
                (collection_name, term, doc_id)
            )

    def _extract_search_terms(self, document: Dict[str, Any]) -> List[str]:
        """从文档中提取搜索词

        Args:
            document: 文档内容

        Returns:
            搜索词列表
        """
        terms = set()

        def extract_from_value(value):
            if isinstance(value, str):
                # 简单的分词：按空格分割并转为小写
                for word in value.lower().split():
                    # 过滤掉太短的词和数字
                    if len(word) > 1 and not word.isdigit():
                        terms.add(word)
            elif isinstance(value, dict):
                for k, v in value.items():
                    extract_from_value(v)
            elif isinstance(value, list):
                for item in value:
                    extract_from_value(item)

        for key, value in document.items():
            # 跳过某些字段
            if key in ['created_at', 'updated_at', 'id']:
                continue
            extract_from_value(value)

        return list(terms)

    def close(self):
        """关闭数据库连接"""
        if hasattr(self.local, 'conn') and self.local.conn is not None:
            self.local.conn.close()
            self.local.conn = None