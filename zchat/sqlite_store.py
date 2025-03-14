import json
import time
import sqlite3
import os
from typing import List, Dict, Any, Optional
import threading

class SQLiteStore:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = None
        self.lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        """Get a thread-safe connection to the database"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _init_db(self):
        """Initialize the database schema"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # Create indexes table to track all indexes
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS indexes (
                name TEXT PRIMARY KEY,
                primary_key TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            ''')

            # Create documents table to store all documents
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                index_name TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (index_name, doc_id)
            )
            ''')

            # Create search terms table for basic search functionality
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_terms (
                index_name TEXT NOT NULL,
                term TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                PRIMARY KEY (index_name, term, doc_id)
            )
            ''')

            # Create indexes for faster searches
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_terms_term ON search_terms (term)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents (updated_at)')

            conn.commit()

    def create_index(self, index_name, options=None):
        """Create a new index"""
        if options is None:
            options = {'primaryKey': 'id'}

        primary_key = options.get('primaryKey', 'id')
        created_at = time.time()

        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # Check if index already exists
            cursor.execute('SELECT name FROM indexes WHERE name = ?', (index_name,))
            if cursor.fetchone() is None:
                cursor.execute(
                    'INSERT INTO indexes (name, primary_key, created_at) VALUES (?, ?, ?)',
                    (index_name, primary_key, created_at)
                )
                conn.commit()

        return {"status": "success", "indexUid": index_name}

    def delete_index(self, index_name):
        """Delete an index and all its documents"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # Delete the index
            cursor.execute('DELETE FROM indexes WHERE name = ?', (index_name,))

            # Delete all documents in the index
            cursor.execute('DELETE FROM documents WHERE index_name = ?', (index_name,))

            # Delete all search terms for the index
            cursor.execute('DELETE FROM search_terms WHERE index_name = ?', (index_name,))

            conn.commit()

        return {"status": "success"}

    def get_indexes(self):
        """Get all indexes"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()
            cursor.execute('SELECT name, primary_key, created_at FROM indexes')

            results = []
            for row in cursor.fetchall():
                results.append({
                    "uid": row['name'],
                    "primaryKey": row['primary_key'],
                    "created_at": row['created_at']
                })

        return {"results": results}

    def add_document(self, index_name, document):
        """Add a document to an index"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # Get the primary key for this index
            cursor.execute('SELECT primary_key FROM indexes WHERE name = ?', (index_name,))
            row = cursor.fetchone()
            if row is None:
                # Create the index if it doesn't exist
                self.create_index(index_name)
                primary_key = 'id'
            else:
                primary_key = row['primary_key']

            if primary_key not in document:
                raise ValueError(f"Document must contain primary key '{primary_key}'")

            doc_id = str(document[primary_key])
            content = json.dumps(document)
            now = time.time()

            # Insert or replace the document
            cursor.execute(
                '''
                INSERT OR REPLACE INTO documents
                (index_name, doc_id, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (index_name, doc_id, content, now, now)
            )

            # Update search terms
            self._update_search_terms(cursor, index_name, doc_id, document)

            conn.commit()

        return {"status": "success", "documentId": doc_id}

    def update_document(self, index_name, document):
        """Update a document in an index"""
        return self.add_document(index_name, document)

    def get_document(self, index_name, doc_id):
        """Get a document by ID"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT content FROM documents WHERE index_name = ? AND doc_id = ?',
                (index_name, doc_id)
            )

            row = cursor.fetchone()
            if row:
                return json.loads(row['content'])

        return None

    def delete_document(self, index_name, doc_id):
        """Delete a document by ID"""
        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # Get the document first to remove search terms
            cursor.execute(
                'SELECT content FROM documents WHERE index_name = ? AND doc_id = ?',
                (index_name, doc_id)
            )

            row = cursor.fetchone()
            if row:
                document = json.loads(row['content'])

                # Delete the document
                cursor.execute(
                    'DELETE FROM documents WHERE index_name = ? AND doc_id = ?',
                    (index_name, doc_id)
                )

                # Delete search terms
                cursor.execute(
                    'DELETE FROM search_terms WHERE index_name = ? AND doc_id = ?',
                    (index_name, doc_id)
                )

                conn.commit()

        return {"status": "success"}

    def _update_search_terms(self, cursor, index_name, doc_id, document):
        """Extract and store search terms for a document"""
        # First, remove existing terms for this document
        cursor.execute(
            'DELETE FROM search_terms WHERE index_name = ? AND doc_id = ?',
            (index_name, doc_id)
        )

        # Extract searchable terms
        terms = self._extract_searchable_terms(document)

        # Insert new terms
        for term in terms:
            cursor.execute(
                'INSERT INTO search_terms (index_name, term, doc_id) VALUES (?, ?, ?)',
                (index_name, term, doc_id)
            )

    def _extract_searchable_terms(self, document):
        """Extract searchable terms from a document"""
        terms = set()

        def extract_terms(obj):
            if isinstance(obj, str):
                # Split by non-alphanumeric characters and convert to lowercase
                for term in ''.join(c if c.isalnum() else ' ' for c in obj).lower().split():
                    if term and len(term) > 1:  # Skip single-character terms
                        terms.add(term)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_terms(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_terms(item)

        extract_terms(document)
        return terms

    def search(self, index_name, query, options=None):
        """Search for documents matching the query"""
        if options is None:
            options = {}

        offset = options.get('offset', 0)
        limit = options.get('limit', 20)
        filters = options.get('filter', [])
        sort = options.get('sort', [])

        conn = self._get_connection()
        with self.lock:
            cursor = conn.cursor()

            # If query is empty, get all documents
            if not query:
                return self._get_all_documents(cursor, index_name, offset, limit, filters, sort)

            # Split the query into terms
            query_terms = ''.join(c if c.isalnum() else ' ' for c in query).lower().split()

            # Find documents that match all query terms
            matching_doc_ids = None
            for term in query_terms:
                cursor.execute(
                    '''
                    SELECT DISTINCT doc_id FROM search_terms
                    WHERE index_name = ? AND term LIKE ?
                    ''',
                    (index_name, f"%{term}%")
                )

                term_doc_ids = {row['doc_id'] for row in cursor.fetchall()}

                if matching_doc_ids is None:
                    matching_doc_ids = term_doc_ids
                else:
                    matching_doc_ids &= term_doc_ids

                if not matching_doc_ids:
                    break

            if not matching_doc_ids:
                return {"hits": [], "offset": offset, "limit": limit, "estimatedTotalHits": 0}

            # Get the matching documents
            placeholders = ','.join(['?'] * len(matching_doc_ids))
            query_params = [index_name] + list(matching_doc_ids)

            cursor.execute(
                f'''
                SELECT doc_id, content FROM documents
                WHERE index_name = ? AND doc_id IN ({placeholders})
                ''',
                query_params
            )

            hits = []
            for row in cursor.fetchall():
                doc = json.loads(row['content'])
                if self._passes_filters(doc, filters):
                    hits.append(doc)

            # Apply sorting
            if sort:
                hits = self._apply_sorting(hits, sort)

            # Apply pagination
            total_hits = len(hits)
            hits = hits[offset:offset+limit]

            return {
                "hits": hits,
                "offset": offset,
                "limit": limit,
                "estimatedTotalHits": total_hits
            }

    def _get_all_documents(self, cursor, index_name, offset, limit, filters, sort):
        """Get all documents in an index with pagination and filtering"""
        cursor.execute(
            'SELECT content FROM documents WHERE index_name = ? ORDER BY updated_at DESC',
            (index_name,)
        )

        hits = []
        for row in cursor.fetchall():
            doc = json.loads(row['content'])
            if self._passes_filters(doc, filters):
                hits.append(doc)

        # Apply sorting
        if sort:
            hits = self._apply_sorting(hits, sort)

        # Apply pagination
        total_hits = len(hits)
        hits = hits[offset:offset+limit]

        return {
            "hits": hits,
            "offset": offset,
            "limit": limit,
            "estimatedTotalHits": total_hits
        }

    def _passes_filters(self, doc, filters):
        """Check if a document passes all filters"""
        if not filters:
            return True

        for filter_str in filters:
            if not self._passes_filter(doc, filter_str):
                return False

        return True

    def _passes_filter(self, doc, filter_str):
        """Check if a document passes a single filter"""
        # Simple filter parsing for equality filters (field=value)
        if '=' in filter_str:
            field, value = filter_str.split('=', 1)

            # Handle nested fields with dot notation
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

    def _apply_sorting(self, hits, sort_fields):
        """Sort hits based on sort fields"""
        for sort_field in reversed(sort_fields):
            reverse = False
            field = sort_field

            if ':' in sort_field:
                field, direction = sort_field.split(':', 1)
                reverse = direction.lower() == 'desc'

            # Sort based on the field
            hits.sort(key=lambda doc: self._get_sort_key(doc, field), reverse=reverse)

        return hits

    def _get_sort_key(self, doc, field):
        """Get the sort key for a document"""
        # Handle nested fields with dot notation
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