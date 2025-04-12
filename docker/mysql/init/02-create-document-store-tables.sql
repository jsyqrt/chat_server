-- 文档存储相关表
CREATE TABLE IF NOT EXISTS collections (
    name VARCHAR(100) PRIMARY KEY,
    primary_key VARCHAR(100) NOT NULL,
    created_at DOUBLE NOT NULL,
    options TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    collection_name VARCHAR(100) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    content LONGTEXT NOT NULL,
    created_at DOUBLE NOT NULL,
    updated_at DOUBLE NOT NULL,
    PRIMARY KEY (collection_name, doc_id),
    CONSTRAINT fk_coll_name FOREIGN KEY (collection_name)
    REFERENCES collections(name) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS indexed_fields (
    collection_name VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (collection_name, field_name),
    CONSTRAINT fk_idx_coll_name FOREIGN KEY (collection_name)
    REFERENCES collections(name) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建索引值表 - 减少VARCHAR长度以避免键长度超出限制
CREATE TABLE IF NOT EXISTS field_values (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    collection_name VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_value VARCHAR(100) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    UNIQUE KEY unique_field_value (collection_name, field_name, field_value(50), doc_id),
    CONSTRAINT fk_field_doc FOREIGN KEY (collection_name, doc_id)
    REFERENCES documents(collection_name, doc_id) ON DELETE CASCADE,
    CONSTRAINT fk_field_idx FOREIGN KEY (collection_name, field_name)
    REFERENCES indexed_fields(collection_name, field_name) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建索引以加快查询
CREATE INDEX idx_documents_updated ON documents (updated_at);
CREATE INDEX idx_field_values_value ON field_values (field_value(50));
CREATE INDEX idx_field_values_lookup ON field_values (collection_name, field_name, doc_id);