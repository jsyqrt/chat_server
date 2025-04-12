#!/usr/bin/env python3
"""
数据库管理脚本

这个脚本提供了统一的命令行界面，用于管理Zchat应用的所有数据库相关操作：
- MySQL数据库的初始化和迁移管理
- MongoDB集合和索引管理
- MeiliSearch索引管理
- 数据库备份和恢复
- 数据库状态检查和故障排除

此脚本整合并替代了之前的db_init.py和database_maintenance.py。
"""

import os
import sys
import argparse
import subprocess
import logging
import shutil
import time
import tarfile
import json
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("db_manager")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BACKUP_DIR = PROJECT_ROOT / "backups"

# 确保备份目录存在
BACKUP_DIR.mkdir(exist_ok=True)

def setup_env():
    """设置环境并添加项目路径"""
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault('FLASK_APP', 'zchat')

def import_app():
    """导入应用并创建实例"""
    try:
        from zchat import create_app

        # 设置基本配置（从docker-compose.yml中获取）
        os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://zchat:zchat_password@localhost:3306/zchat')
        os.environ.setdefault('MONGODB_URI', 'mongodb://zchat:zchat_password@localhost:27017/')
        os.environ.setdefault('MONGODB_DB', 'zchat')
        os.environ.setdefault('MEILISEARCH_HOST', 'http://localhost:7700')
        os.environ.setdefault('MEILISEARCH_KEY', 'aSampleMasterKey')

        app = create_app()
        logger.info("应用导入成功")
        return app
    except ImportError as e:
        logger.error(f"导入应用失败: {e}")
        sys.exit(1)

def get_db_and_models(app):
    """获取数据库对象和模型"""
    with app.app_context():
        from zchat.models.base import db
        # 确保所有模型都被导入
        import zchat.models
        return db

# ========== MySQL数据库管理函数 ==========

def init_mysql(args):
    """初始化MySQL数据库"""
    app = import_app()

    with app.app_context():
        db = get_db_and_models(app)

        # 检查migrations目录
        migrations_dir = PROJECT_ROOT / 'migrations'
        if not migrations_dir.exists() or not any(migrations_dir.iterdir()):
            logger.info("初始化迁移环境")
            subprocess.run(['flask', 'db', 'init'], check=True)

        # 检查是否有现有迁移
        versions_dir = migrations_dir / 'versions'
        if not versions_dir.exists() or not any(versions_dir.iterdir()):
            logger.info("创建初始迁移")
            subprocess.run(['flask', 'db', 'migrate', '-m', "Initial migration"], check=True)

        # 应用迁移
        logger.info("应用迁移")
        subprocess.run(['flask', 'db', 'upgrade'], check=True)

        logger.info("MySQL数据库初始化完成")

def check_mysql_status(args):
    """检查MySQL数据库状态"""
    app = import_app()

    with app.app_context():
        db = get_db_and_models(app)

        # 获取所有表
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print("=== MySQL数据库状态 ===")
        print(f"数据库URI: {db.engine.url}")
        print(f"表数量: {len(tables)}")

        for table in tables:
            print(f"  - {table}")

        # 检查迁移状态
        if 'alembic_version' in tables:
            from sqlalchemy import text
            version = None
            try:
                with db.engine.connect() as conn:
                    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                print("无法读取迁移版本")

            if version:
                print(f"当前迁移版本: {version}")

                # 检查是否是最新版本
                try:
                    result = subprocess.run(
                        ['flask', 'db', 'heads'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    head = result.stdout.strip()
                    if version in head:
                        print("迁移状态: 最新")
                    else:
                        print(f"迁移状态: 需要更新 (最新版本: {head})")
                except Exception as e:
                    print(f"检查迁移头失败: {e}")
        else:
            print("警告: 迁移跟踪表(alembic_version)不存在")

def reset_mysql_migrations(args):
    """重置MySQL迁移"""
    if not args.force:
        print("警告: 此操作将删除迁移历史并重新初始化。已有数据不会丢失，但迁移历史将重置。")
        confirm = input("是否继续? (y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return

    migrations_dir = PROJECT_ROOT / 'migrations'
    if migrations_dir.exists():
        shutil.rmtree(migrations_dir)
        print("已删除migrations目录")

    # 初始化MySQL
    init_mysql(args)
    print("迁移已重置")

# ========== 文档存储管理函数 ==========

def init_document_store(args):
    """初始化文档存储数据库"""
    try:
        from flask import current_app
        from zchat.storage.api import create_initial_collections

        logger.info("正在初始化文档存储...")
        # 创建必要的集合
        create_initial_collections(current_app)

        logger.info("文档存储初始化完成")
        return True
    except Exception as e:
        logger.error(f"文档存储初始化失败: {e}")
        return False

def check_document_store_status(args):
    """检查文档存储状态"""
    try:
        from flask import current_app

        print("=== 文档存储状态 ===")
        print(f"文档存储类型: {current_app.config['DOCUMENT_STORE_TYPE']}")

        if current_app.config['DOCUMENT_STORE_TYPE'] == 'mysql':
            # MySQL文档存储
            mysql_config = current_app.config.get('DOCUMENT_STORE_CONFIG', {})
            print(f"MySQL主机: {mysql_config.get('host', 'unknown')}")
            print(f"MySQL数据库: {mysql_config.get('db_name', 'unknown')}")
        else:
            # SQLite文档存储或其他类型
            print(f"存储配置: {current_app.config['DOCUMENT_STORE_CONFIG']}")

        # 获取集合信息
        collections = current_app.document_store.list_collections()
        print("\n集合数量:", len(collections.get('collections', [])))

        for coll in collections.get('collections', []):
            print(f"集合: {coll.get('name')} (主键: {coll.get('primaryKey')})")

        return True
    except Exception as e:
        print(f"检查文档存储状态失败: {e}")
        return False

def backup_document_store(args):
    """备份文档存储数据库"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = BACKUP_DIR / f"document_store_backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        from flask import current_app

        # 导出所有集合的数据
        collections = current_app.document_store.list_collections()
        for coll in collections.get('collections', []):
            coll_name = coll.get('name')
            if coll_name:
                # 搜索该集合中的所有文档
                results = current_app.document_store.search(coll_name, '', {'limit': 1000})
                documents = results.get('hits', [])

                # 将文档保存到JSON文件
                coll_file = backup_dir / f"{coll_name}.json"
                with open(coll_file, 'w', encoding='utf-8') as f:
                    json.dump(documents, f, ensure_ascii=False, indent=2)

                logger.info(f"已备份集合 {coll_name} 中的 {len(documents)} 个文档")

        # 备份集合元数据
        with open(backup_dir / "collections_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(collections, f, ensure_ascii=False, indent=2)

        logger.info(f"文档存储备份已创建: {backup_dir}")
        return str(backup_dir)
    except Exception as e:
        logger.error(f"文档存储备份失败: {e}")
        return None

def restore_document_store(args):
    """恢复文档存储数据库"""
    try:
        backup_dir = args.directory
        if not backup_dir or not os.path.isdir(backup_dir):
            logger.error("需要指定文档存储备份目录 (--directory)")
            return False

        from flask import current_app
        import json

        # 读取集合元数据
        metadata_file = os.path.join(backup_dir, "collections_metadata.json")
        if not os.path.exists(metadata_file):
            logger.error(f"备份目录中缺少元数据文件: {metadata_file}")
            return False

        with open(metadata_file, 'r', encoding='utf-8') as f:
            collections_metadata = json.load(f)

        # 恢复集合
        for coll in collections_metadata.get('collections', []):
            coll_name = coll.get('name')
            if not coll_name:
                continue

            # 创建集合（如果不存在）
            options = coll.get('options', {})
            try:
                # 尝试创建集合
                current_app.document_store.create_collection(
                    coll_name,
                    {
                        'primaryKey': coll.get('primaryKey', 'id'),
                        'indexedFields': options.get('indexedFields', [])
                    }
                )
                logger.info(f"创建集合: {coll_name}")
            except Exception as e:
                logger.warning(f"创建集合 {coll_name} 失败，可能已存在: {str(e)}")

            # 恢复文档
            coll_file = os.path.join(backup_dir, f"{coll_name}.json")
            if os.path.exists(coll_file):
                with open(coll_file, 'r', encoding='utf-8') as f:
                    documents = json.load(f)

                # 恢复文档到集合
                for doc in documents:
                    try:
                        # 尝试先删除可能存在的文档
                        doc_id = doc.get(coll.get('primaryKey', 'id'))
                        if doc_id:
                            current_app.document_store.delete_document(coll_name, doc_id)
                        # 添加文档
                        current_app.document_store.add_document(coll_name, doc)
                    except Exception as e:
                        logger.warning(f"恢复文档到集合 {coll_name} 失败: {str(e)}")

                logger.info(f"已恢复 {len(documents)} 个文档到集合 {coll_name}")

        logger.info(f"文档存储数据已从 {backup_dir} 恢复")
        return True
    except Exception as e:
        logger.error(f"文档存储恢复失败: {e}")
        return False

# ========== MeiliSearch管理函数 ==========

def init_search(args):
    """初始化MeiliSearch"""
    app = import_app()

    with app.app_context():
        try:
            # 假设meili模块包含初始化搜索引擎的功能
            from zchat import meili
            meili.init_indexes()
            logger.info("MeiliSearch初始化完成")
        except Exception as e:
            logger.error(f"MeiliSearch初始化失败: {e}")

def check_search_status(args):
    """检查MeiliSearch状态"""
    app = import_app()

    with app.app_context():
        try:
            from zchat import meili

            print("=== MeiliSearch状态 ===")
            print(f"MeiliSearch URL: {app.config.get('MEILISEARCH_URL')}")

            # 检查索引
            indexes = meili.get_client().get_indexes()
            print(f"索引数量: {len(indexes)}")

            for idx in indexes:
                print(f"  - {idx.uid} (文档数: {idx.get_stats()['numberOfDocuments']})")
        except Exception as e:
            print(f"检查MeiliSearch状态失败: {e}")

# ========== 备份和恢复函数 ==========

def backup_mysql(args):
    """备份MySQL数据库"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"mysql_backup_{timestamp}.sql"

    # 使用mysqldump创建备份
    try:
        # 从应用获取数据库配置
        app = import_app()
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        # 解析URI
        if '+' in db_uri:
            db_uri = db_uri.split('+')[0] + db_uri.split('+')[1].split('://')[-1]

        parts = db_uri.replace('mysql://', '').split('@')
        auth = parts[0].split(':')
        host_db = parts[1].split('/')

        user = auth[0]
        password = auth[1]
        host = host_db[0]
        db_name = host_db[1]

        # 执行mysqldump命令
        cmd = [
            "mysqldump",
            f"-h{host}",
            f"-u{user}",
            f"-p{password}",
            db_name
        ]

        with open(backup_file, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)

        logger.info(f"MySQL备份已创建: {backup_file}")
        return str(backup_file)
    except Exception as e:
        logger.error(f"MySQL备份失败: {e}")
        if backup_file.exists():
            backup_file.unlink()
        return None

def create_full_backup(args):
    """创建完整备份"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"zchat_backup_{timestamp}"
        temp_dir = BACKUP_DIR / backup_name
        temp_dir.mkdir(exist_ok=True)

        # 备份MySQL
        mysql_backup = backup_mysql(args)
        if mysql_backup:
            shutil.copy(mysql_backup, temp_dir)

        # 备份文档存储
        document_store_backup = backup_document_store(args)
        if document_store_backup:
            shutil.copy(document_store_backup, temp_dir)

        # 创建元数据文件
        metadata = {
            "timestamp": timestamp,
            "mysql_backup": os.path.basename(mysql_backup) if mysql_backup else None,
            "document_store_backup": os.path.basename(document_store_backup) if document_store_backup else None,
            "description": args.description if hasattr(args, 'description') else "自动备份"
        }

        with open(temp_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        # 创建tar归档
        archive_path = BACKUP_DIR / f"{backup_name}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(temp_dir, arcname=backup_name)

        # 清理临时文件
        shutil.rmtree(temp_dir)
        if mysql_backup:
            Path(mysql_backup).unlink(missing_ok=True)
        if document_store_backup:
            shutil.rmtree(document_store_backup, ignore_errors=True)

        logger.info(f"完整备份已创建: {archive_path}")

        # 如果指定了自动清理，删除旧备份
        if args.cleanup:
            cleanup_old_backups(args)

        return str(archive_path)
    except Exception as e:
        logger.error(f"创建完整备份失败: {e}")
        return None

def cleanup_old_backups(args):
    """清理旧备份"""
    try:
        # 获取所有tar.gz备份
        backups = sorted([f for f in BACKUP_DIR.glob("zchat_backup_*.tar.gz")])

        # 保留的备份数量
        keep_count = args.keep if hasattr(args, 'keep') and args.keep else 5

        # 如果备份数量超过保留数量，删除旧的
        if len(backups) > keep_count:
            for old_backup in backups[:-keep_count]:
                old_backup.unlink()
                logger.info(f"已删除旧备份: {old_backup}")
    except Exception as e:
        logger.error(f"清理旧备份失败: {e}")

def restore_mysql(args):
    """恢复MySQL数据库"""
    if not args.file:
        logger.error("需要指定MySQL备份文件 (--file)")
        return False

    backup_file = Path(args.file)
    if not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return False

    try:
        # 从应用获取数据库配置
        app = import_app()
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        # 解析URI
        if '+' in db_uri:
            db_uri = db_uri.split('+')[0] + db_uri.split('+')[1].split('://')[-1]

        parts = db_uri.replace('mysql://', '').split('@')
        auth = parts[0].split(':')
        host_db = parts[1].split('/')

        user = auth[0]
        password = auth[1]
        host = host_db[0]
        db_name = host_db[1]

        # 执行mysql命令恢复
        cmd = [
            "mysql",
            f"-h{host}",
            f"-u{user}",
            f"-p{password}",
            db_name
        ]

        with open(backup_file, 'r') as f:
            subprocess.run(cmd, stdin=f, check=True)

        logger.info(f"MySQL数据已从 {backup_file} 恢复")
        return True
    except Exception as e:
        logger.error(f"MySQL恢复失败: {e}")
        return False

def restore_full_backup(args):
    """恢复完整备份"""
    if not args.file and not args.latest:
        # 如果未指定文件，尝试使用最新的备份
        backups = sorted([f for f in BACKUP_DIR.glob("zchat_backup_*.tar.gz")])
        if not backups:
            logger.error("未找到备份文件")
            return False
        backup_file = backups[-1]
        logger.info(f"使用最新备份: {backup_file}")
    else:
        backup_file = Path(args.file)

    if not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return False

    try:
        # 创建临时目录解压备份
        temp_dir = BACKUP_DIR / "temp_restore"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        # 解压备份
        with tarfile.open(backup_file, "r:gz") as tar:
            tar.extractall(path=temp_dir)

        # 找到解压后的目录（应该只有一个子目录）
        extract_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
        if not extract_dirs:
            logger.error("备份文件格式错误")
            return False

        extract_dir = extract_dirs[0]

        # 读取元数据
        try:
            with open(extract_dir / "metadata.json", 'r') as f:
                metadata = json.load(f)
        except:
            metadata = {}

        # 恢复MySQL
        mysql_backup = None
        for sql_file in extract_dir.glob("*.sql"):
            mysql_backup = sql_file
            break

        if mysql_backup:
            mysql_args = argparse.Namespace()
            mysql_args.file = str(mysql_backup)
            if not restore_mysql(mysql_args):
                logger.warning("MySQL恢复失败")

        # 恢复文档存储
        document_store_backup = extract_dir / "document_store_backup"
        if document_store_backup.exists() and document_store_backup.is_dir():
            document_store_args = argparse.Namespace()
            document_store_args.directory = str(document_store_backup)
            if not restore_document_store(document_store_args):
                logger.warning("文档存储恢复失败")

        # 清理临时目录
        shutil.rmtree(temp_dir)

        logger.info(f"从 {backup_file} 恢复完成")
        return True
    except Exception as e:
        logger.error(f"恢复失败: {e}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return False

# ========== 综合管理函数 ==========

def init_all(args):
    """初始化所有数据库"""
    # 设置环境
    setup_env()

    # 初始化MySQL
    logger.info("初始化MySQL...")
    init_mysql(args)

    # 初始化文档存储
    logger.info("初始化文档存储...")
    init_document_store(args)

    # 初始化MeiliSearch
    logger.info("初始化MeiliSearch...")
    init_search(args)

    logger.info("所有数据库初始化完成")

def check_all_status(args):
    """检查所有数据库状态"""
    # 设置环境
    setup_env()

    # 检查MySQL
    check_mysql_status(args)
    print("\n")

    # 检查文档存储
    check_document_store_status(args)
    print("\n")

    # 检查MeiliSearch
    check_search_status(args)

def fix_database(args):
    """修复数据库问题"""
    # 设置环境
    setup_env()
    app = import_app()

    with app.app_context():
        from zchat.db import manage_db_migrations, init_all_db

        try:
            # 尝试管理迁移
            logger.info("尝试修复数据库迁移...")
            manage_db_migrations()

            # 尝试初始化所有数据库
            logger.info("尝试初始化所有数据库...")
            init_all_db()

            logger.info("数据库修复完成")
            return True
        except Exception as e:
            logger.error(f"自动修复失败: {e}")
            return False

def validate_database(args):
    """验证数据库结构与模型的一致性"""
    # 设置环境
    setup_env()
    app = import_app()

    with app.app_context():
        # 导入并创建db实例
        db = get_db_and_models(app)

        # 从应用获取模型类
        from zchat.models import User, AdminUser  # 示例模型

        # 检查核心表存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        core_tables = ['user', 'admin_user']
        missing_tables = [table for table in core_tables if table.lower() not in [t.lower() for t in tables]]

        if missing_tables:
            logger.error(f"验证失败: 缺少核心表 {', '.join(missing_tables)}")
            return False

        # 检查迁移状态
        logger.info("检查迁移状态...")
        try:
            # 检查当前版本
            current_cmd = subprocess.run(
                ['flask', 'db', 'current'],
                check=True,
                capture_output=True,
                text=True
            )
            current = current_cmd.stdout.strip()

            # 检查最新版本
            heads_cmd = subprocess.run(
                ['flask', 'db', 'heads'],
                check=True,
                capture_output=True,
                text=True
            )
            heads = heads_cmd.stdout.strip()

            if current not in heads:
                logger.warning(f"迁移不是最新版本: 当前 {current}, 最新 {heads}")
                return False
        except Exception as e:
            logger.error(f"检查迁移状态失败: {e}")
            return False

        logger.info("数据库验证通过")
        return True

# ========== 命令行界面 ==========

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(
        description="Zchat数据库管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # 初始化命令
    init_parser = subparsers.add_parser("init-all", help="初始化所有数据库")

    init_mysql_parser = subparsers.add_parser("init-mysql", help="初始化MySQL数据库")

    init_document_store_parser = subparsers.add_parser("init-document-store", help="初始化文档存储数据库")

    init_search_parser = subparsers.add_parser("init-search", help="初始化MeiliSearch")

    # 状态命令
    status_parser = subparsers.add_parser("status", help="检查所有数据库状态")

    mysql_status_parser = subparsers.add_parser("mysql-status", help="检查MySQL状态")

    document_store_status_parser = subparsers.add_parser("document-store-status", help="检查文档存储状态")

    search_status_parser = subparsers.add_parser("search-status", help="检查MeiliSearch状态")

    # 迁移管理命令
    reset_migrations_parser = subparsers.add_parser("reset-migrations", help="重置数据库迁移（谨慎使用）")
    reset_migrations_parser.add_argument("--force", action="store_true", help="不提示确认")

    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="创建完整备份")
    backup_parser.add_argument("--description", help="备份描述")
    backup_parser.add_argument("--cleanup", action="store_true", help="清理旧备份")
    backup_parser.add_argument("--keep", type=int, default=5, help="保留的备份数量")

    backup_mysql_parser = subparsers.add_parser("backup-mysql", help="备份MySQL数据库")

    backup_document_store_parser = subparsers.add_parser("backup-document-store", help="备份文档存储数据库")

    # 恢复命令
    restore_parser = subparsers.add_parser("restore", help="从备份恢复")
    restore_parser.add_argument("--file", help="备份文件路径")
    restore_parser.add_argument("--latest", action="store_true", help="使用最新备份")

    restore_mysql_parser = subparsers.add_parser("restore-mysql", help="恢复MySQL数据库")
    restore_mysql_parser.add_argument("--file", required=True, help="MySQL备份文件")

    restore_document_store_parser = subparsers.add_parser("restore-document-store", help="恢复文档存储数据库")
    restore_document_store_parser.add_argument("--directory", required=True, help="文档存储备份目录")

    # 维护命令
    fix_parser = subparsers.add_parser("fix", help="尝试修复数据库问题")

    validate_parser = subparsers.add_parser("validate", help="验证数据库结构")

    # 解析参数
    args = parser.parse_args()

    # 设置环境
    setup_env()

    # 处理命令
    if args.command == "init-all":
        init_all(args)
    elif args.command == "init-mysql":
        init_mysql(args)
    elif args.command == "init-document-store":
        init_document_store(args)
    elif args.command == "init-search":
        init_search(args)
    elif args.command == "status":
        check_all_status(args)
    elif args.command == "mysql-status":
        check_mysql_status(args)
    elif args.command == "document-store-status":
        check_document_store_status(args)
    elif args.command == "search-status":
        check_search_status(args)
    elif args.command == "reset-migrations":
        reset_mysql_migrations(args)
    elif args.command == "backup":
        create_full_backup(args)
    elif args.command == "backup-mysql":
        backup_mysql(args)
    elif args.command == "backup-document-store":
        backup_document_store(args)
    elif args.command == "restore":
        restore_full_backup(args)
    elif args.command == "restore-mysql":
        restore_mysql(args)
    elif args.command == "restore-document-store":
        restore_document_store(args)
    elif args.command == "fix":
        fix_database(args)
    elif args.command == "validate":
        validate_database(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()