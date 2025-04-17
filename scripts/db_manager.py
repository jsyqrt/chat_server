#!/usr/bin/env python3
"""
数据库管理脚本

这个脚本提供了统一的命令行界面，用于管理Zchat应用的所有数据库相关操作：
- MySQL数据库的初始化和迁移管理（包含文档存储）
- MongoDB文档存储的管理
- 数据库备份和恢复
- 数据库状态检查和故障排除

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
from urllib.parse import urlparse
from tqdm import tqdm  # 进度条库
import threading
import io
import tempfile

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("db_manager")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BACKUP_DIR = PROJECT_ROOT / "instance" / "backups"

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
        os.environ.setdefault('DOCUMENT_STORE_TYPE', 'mysql')  # 默认使用MySQL文档存储

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

# ========== 备份和恢复函数 ==========

def backup_mysql(args):
    """备份MySQL数据库"""
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"mysql_backup_{timestamp}.sql"

    # 使用mysqldump创建备份
    try:
        # 从应用获取数据库配置
        logger.info("开始MySQL备份过程...")
        app = import_app()
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        logger.info(f"使用数据库URI: {db_uri}")

        # 解析URI (更稳健的方式)
        parsed_url = urlparse(db_uri)

        # 从netlog中解析出用户名和密码
        credentials = parsed_url.netloc.split('@')[0]
        user, password = credentials.split(':')

        # 解析主机和端口
        if '@' in parsed_url.netloc:
            host_port = parsed_url.netloc.split('@')[1].split('/')[0]
        else:
            host_port = parsed_url.netloc.split('/')[0]

        if ':' in host_port:
            host, port = host_port.split(':')
        else:
            host = host_port
            port = '3306'

        # 获取数据库名称
        db_name = parsed_url.path.strip('/')

        logger.info(f"解析结果: 用户={user}, 主机={host}, 端口={port}, 数据库={db_name}")

        # 执行mysqldump命令 (简化选项以提高兼容性)
        cmd = [
            "mysqldump",
            f"-h{host}",
            f"-P{port}",
            f"-u{user}",
            f"-p{password}",
            "--no-tablespaces",
            "--verbose",  # 添加详细输出
            db_name
        ]

        logger.info("执行MySQL导出命令...")

        # 创建进度显示函数
        def show_progress():
            spinner = ['|', '/', '-', '\\']
            counter = 0
            # 检查备份文件大小作为进度指示器
            pbar = tqdm(total=100, desc="MySQL备份进度", unit="%")
            last_size = 0
            while True:
                if not backup_file.exists():
                    time.sleep(0.5)
                    continue

                current_size = backup_file.stat().st_size
                if current_size > last_size:
                    # 更新进度条 (假设每次增量为总进度的一小部分)
                    increment = min(5, 100 - pbar.n)  # 至少移动一点，但不超过100%
                    pbar.update(increment)
                    last_size = current_size

                    # 添加更多日志信息
                    if pbar.n % 20 == 0:  # 每增加20%记录一次日志
                        logger.info(f"MySQL备份进行中... ({pbar.n}% 完成，当前大小: {current_size/1024/1024:.2f} MB)")

                if pbar.n >= 100:
                    break

                time.sleep(1)
                counter = (counter + 1) % 4
                pbar.set_description(f"MySQL备份进度 {spinner[counter]}")

            pbar.close()

        # 启动进度线程
        progress_thread = threading.Thread(target=show_progress)
        progress_thread.daemon = True
        progress_thread.start()

        # 捕获stderr输出作为额外的日志
        process = subprocess.Popen(
            cmd,
            stdout=open(backup_file, 'w'),
            stderr=subprocess.PIPE,
            text=True
        )

        # 处理stderr输出
        for line in process.stderr:
            if line.strip():
                logger.info(f"mysqldump: {line.strip()}")

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mysqldump 进程退出，错误码: {exit_code}")

        # 等待进度线程完成
        if progress_thread.is_alive():
            time.sleep(2)  # 给进度线程一点时间结束

        # 计算总用时
        elapsed_time = time.time() - start_time
        final_size = backup_file.stat().st_size / (1024 * 1024)  # 转换为MB
        logger.info(f"MySQL备份已创建: {backup_file} (大小: {final_size:.2f} MB, 用时: {elapsed_time:.2f} 秒)")
        return str(backup_file)
    except Exception as e:
        logger.error(f"MySQL备份失败: {e}")
        if backup_file.exists():
            backup_file.unlink()
        return None

def create_full_backup(args):
    """创建完整备份"""
    start_time = time.time()
    try:
        logger.info("开始创建完整备份...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"zchat_backup_{timestamp}"
        temp_dir = BACKUP_DIR / backup_name
        temp_dir.mkdir(exist_ok=True)

        # 获取应用实例，以确定当前文档存储类型
        app = import_app()
        document_store_type = app.config.get('DOCUMENT_STORE_TYPE', 'mysql')

        # 备份MySQL
        logger.info("第1步: 备份MySQL数据库...")
        mysql_backup = backup_mysql(args)
        if mysql_backup:
            shutil.copy(mysql_backup, temp_dir)
            logger.info(f"MySQL备份已复制到临时目录: {temp_dir}")
        else:
            logger.warning("MySQL备份失败，将继续但不包含MySQL数据")

        # 如果使用MongoDB存储，备份MongoDB
        mongodb_backup = None
        if document_store_type == 'mongodb':
            logger.info("第2步: 备份MongoDB数据库...")
            mongodb_backup = backup_mongodb(args)
            if mongodb_backup:
                shutil.copy(mongodb_backup, temp_dir)
                logger.info(f"MongoDB备份已复制到临时目录: {temp_dir}")
            else:
                logger.warning("MongoDB备份失败，将继续但不包含MongoDB数据")

        # 创建元数据文件
        logger.info("第3步: 创建元数据文件...")
        metadata = {
            "timestamp": timestamp,
            "mysql_backup": os.path.basename(mysql_backup) if mysql_backup else None,
            "mongodb_backup": os.path.basename(mongodb_backup) if mongodb_backup else None,
            "document_store_type": document_store_type,
            "description": args.description if hasattr(args, 'description') else "自动备份",
            "created_at": datetime.now().isoformat(),
            "backup_version": "1.2"  # 更新版本号以支持MongoDB
        }

        with open(temp_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
            logger.info("元数据文件已创建")

        # 创建tar归档
        logger.info("第4步: 创建tar归档...")
        archive_path = BACKUP_DIR / f"{backup_name}.tar.gz"

        # 获取总文件大小，用于进度条
        total_size = sum(f.stat().st_size for f in temp_dir.glob('**/*') if f.is_file())

        with tqdm(total=100, desc="创建备份归档", unit="%") as pbar:
            # 使用自定义的tarfile.add函数，添加进度回调
            def custom_add(tarobj, name, arcname):
                original_add = tarobj.add
                processed_size = [0]

                def update_progress(size):
                    processed_size[0] += size
                    progress = min(int(processed_size[0] / total_size * 100), 100)
                    # 更新进度条
                    pbar.update(progress - pbar.n)
                    # 每处理20%记录一次日志
                    if progress % 20 == 0 and progress > 0:
                        logger.info(f"归档进度: {progress}% 完成")

                # 拦截tarinfo处理以更新进度
                orig_filter = tarobj.filter

                def progress_filter(tarinfo):
                    if tarinfo.isfile():
                        update_progress(tarinfo.size)
                    return orig_filter(tarinfo) if orig_filter else tarinfo

                tarobj.filter = progress_filter
                original_add(name, arcname)
                tarobj.filter = orig_filter

            with tarfile.open(archive_path, "w:gz") as tar:
                custom_add(tar, str(temp_dir), backup_name)

        # 清理临时文件
        logger.info("第5步: 清理临时文件...")
        shutil.rmtree(temp_dir)
        if mysql_backup:
            Path(mysql_backup).unlink(missing_ok=True)
        if mongodb_backup:
            Path(mongodb_backup).unlink(missing_ok=True)
        logger.info("临时备份文件已删除")

        # 计算最终大小和用时
        final_size = archive_path.stat().st_size / (1024 * 1024)  # 转换为MB
        elapsed_time = time.time() - start_time
        logger.info(f"完整备份已创建: {archive_path} (大小: {final_size:.2f} MB, 用时: {elapsed_time:.2f} 秒)")

        # 如果指定了自动清理，删除旧备份
        if args.cleanup:
            logger.info("开始清理旧备份...")
            cleanup_old_backups(args)

        return str(archive_path)
    except Exception as e:
        logger.error(f"创建完整备份失败: {e}")
        elapsed_time = time.time() - start_time
        logger.error(f"备份失败，用时: {elapsed_time:.2f} 秒")
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
    start_time = time.time()

    if not args.file:
        logger.error("需要指定MySQL备份文件 (--file)")
        return False

    backup_file = Path(args.file)
    if not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return False

    try:
        logger.info(f"开始从 {backup_file} 恢复MySQL数据库...")
        # 获取文件大小
        file_size = backup_file.stat().st_size
        logger.info(f"备份文件大小: {file_size/1024/1024:.2f} MB")

        # 从应用获取数据库配置
        app = import_app()
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        logger.info(f"使用数据库URI: {db_uri}")

        # 解析URI (更稳健的方式)
        parsed_url = urlparse(db_uri)

        # 从netlog中解析出用户名和密码
        credentials = parsed_url.netloc.split('@')[0]
        user, password = credentials.split(':')

        # 解析主机和端口
        if '@' in parsed_url.netloc:
            host_port = parsed_url.netloc.split('@')[1].split('/')[0]
        else:
            host_port = parsed_url.netloc.split('/')[0]

        if ':' in host_port:
            host, port = host_port.split(':')
        else:
            host = host_port
            port = '3306'

        # 获取数据库名称
        db_name = parsed_url.path.strip('/')

        logger.info(f"解析结果: 用户={user}, 主机={host}, 端口={port}, 数据库={db_name}")

        # 执行mysql命令恢复 (简化选项以提高兼容性)
        cmd = [
            "mysql",
            f"-h{host}",
            f"-P{port}",
            f"-u{user}",
            f"-p{password}",
            "--verbose",  # 添加详细输出
            db_name
        ]

        # 创建进度线程
        def show_restore_progress():
            with tqdm(total=100, desc="MySQL恢复进度", unit="%") as pbar:
                for i in range(1, 101):
                    time.sleep(0.5)  # 假设恢复过程是均匀的
                    pbar.update(1)
                    # 每20%记录一次日志
                    if i % 20 == 0:
                        logger.info(f"MySQL恢复进度: 大约 {i}% 完成")

        # 启动进度线程
        progress_thread = threading.Thread(target=show_restore_progress)
        progress_thread.daemon = True
        progress_thread.start()

        logger.info("执行MySQL恢复命令...")

        # 执行恢复命令并捕获输出
        process = subprocess.Popen(
            cmd,
            stdin=open(backup_file, 'r'),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )

        # 处理stderr输出作为日志
        for line in process.stderr:
            if line.strip():
                logger.info(f"MySQL恢复: {line.strip()}")

        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"MySQL恢复进程退出，错误码: {exit_code}")

        # 计算用时
        elapsed_time = time.time() - start_time
        logger.info(f"MySQL数据已从 {backup_file} 恢复 (用时: {elapsed_time:.2f} 秒)")
        return True
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"MySQL恢复失败: {e} (用时: {elapsed_time:.2f} 秒)")
        return False

def restore_full_backup(args):
    """恢复完整备份"""
    start_time = time.time()

    if not args.file and not args.latest:
        # 如果未指定文件，尝试使用最新的备份
        backups = sorted([f for f in BACKUP_DIR.glob("zchat_backup_*.tar.gz")])
        if not backups:
            logger.error("未找到备份文件")
            return False
        backup_file = backups[-1]
        logger.info(f"使用最新备份: {backup_file}")
    else:
        backup_file = Path(args.file) if args.file else None

    if backup_file and not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return False

    try:
        logger.info(f"开始恢复备份: {backup_file}")
        file_size = backup_file.stat().st_size
        logger.info(f"备份文件大小: {file_size/1024/1024:.2f} MB")

        # 创建临时目录解压备份
        temp_dir = BACKUP_DIR / "temp_restore"
        if temp_dir.exists():
            logger.info("清理已存在的临时恢复目录...")
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        logger.info(f"创建临时恢复目录: {temp_dir}")

        # 解压备份
        logger.info("第1步: 解压备份文件...")
        with tqdm(total=100, desc="解压备份", unit="%") as pbar:
            # 自定义的解压函数，以支持进度条
            with tarfile.open(backup_file, "r:gz") as tar:
                members = tar.getmembers()
                total_size = sum(m.size for m in members if m.isfile())
                extracted_size = 0

                for member in members:
                    tar.extract(member, path=temp_dir)
                    if member.isfile():
                        extracted_size += member.size
                        progress = min(int(extracted_size / total_size * 100), 100)
                        # 更新进度条
                        pbar.update(progress - pbar.n)
                        # 每处理25%记录一次日志
                        if progress % 25 == 0 and progress > 0 and pbar.n != progress:
                            logger.info(f"解压进度: {progress}% 完成")

        # 找到解压后的目录（应该只有一个子目录）
        extract_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
        if not extract_dirs:
            logger.error("备份文件格式错误: 未找到解压后的目录")
            return False

        extract_dir = extract_dirs[0]
        logger.info(f"备份内容已解压到: {extract_dir}")

        # 读取元数据
        logger.info("第2步: 读取备份元数据...")
        try:
            with open(extract_dir / "metadata.json", 'r') as f:
                metadata = json.load(f)
                logger.info(f"备份元数据: 创建于 {metadata.get('timestamp', '未知')}, 描述: {metadata.get('description', '无')}")
                document_store_type = metadata.get('document_store_type', 'mysql')
                logger.info(f"备份的文档存储类型: {document_store_type}")
        except Exception as e:
            logger.warning(f"读取元数据失败: {e}")
            metadata = {}
            document_store_type = 'mysql'  # 默认假设为MySQL

        # 恢复MySQL
        logger.info("第3步: 恢复MySQL数据库...")
        mysql_backup = None
        for sql_file in extract_dir.glob("*.sql"):
            mysql_backup = sql_file
            break

        if mysql_backup:
            logger.info(f"找到MySQL备份文件: {mysql_backup}")
            mysql_args = argparse.Namespace()
            mysql_args.file = str(mysql_backup)
            if not restore_mysql(mysql_args):
                logger.warning("MySQL恢复失败")
        else:
            logger.warning("未找到MySQL备份文件")

        # 恢复MongoDB（如果备份中存在）
        mongodb_backup = None
        for mongodb_file in extract_dir.glob("mongodb_backup_*.gz"):
            mongodb_backup = mongodb_file
            break

        if document_store_type == 'mongodb' and mongodb_backup:
            logger.info("第4步: 恢复MongoDB数据库...")
            logger.info(f"找到MongoDB备份文件: {mongodb_backup}")
            mongodb_args = argparse.Namespace()
            mongodb_args.file = str(mongodb_backup)
            if not restore_mongodb(mongodb_args):
                logger.warning("MongoDB恢复失败")
        elif document_store_type == 'mongodb':
            logger.warning("未找到MongoDB备份文件，但文档存储类型为MongoDB")

        # 清理临时目录
        logger.info("第5步: 清理临时文件...")
        shutil.rmtree(temp_dir)
        logger.info("临时恢复目录已删除")

        # 计算用时
        elapsed_time = time.time() - start_time
        logger.info(f"从 {backup_file} 恢复完成 (用时: {elapsed_time:.2f} 秒)")
        return True
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"恢复失败: {e} (用时: {elapsed_time:.2f} 秒)")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return False

# ========== MongoDB管理函数 ==========

def init_mongodb(args):
    """初始化MongoDB"""
    app = import_app()

    with app.app_context():
        try:
            # 检查是否配置了MongoDB
            if app.config.get('DOCUMENT_STORE_TYPE') != 'mongodb':
                logger.info("当前文档存储类型不是MongoDB，将临时切换")
                original_store_type = app.config.get('DOCUMENT_STORE_TYPE')
                app.config['DOCUMENT_STORE_TYPE'] = 'mongodb'
            else:
                original_store_type = None

            # 获取MongoDB存储实例
            from zchat.storage.factory import StorageFactory
            mongo_config = {
                'host': app.config.get('MONGODB_HOST', 'localhost'),
                'port': int(app.config.get('MONGODB_PORT', 27017)),
                'username': app.config.get('MONGODB_USER'),
                'password': app.config.get('MONGODB_PASSWORD'),
                'db_name': app.config.get('MONGODB_DB', 'zchat'),
                'auth_source': app.config.get('MONGODB_AUTH_SOURCE', 'admin')
            }
            mongo_store = StorageFactory.create_store('mongodb', **mongo_config)

            # 创建初始集合
            collections_to_create = [
                {
                    'name': 'mindmaps',
                    'options': {
                        'primaryKey': 'id',
                        'indexedFields': ['title', 'created_by', 'difficulty']
                    }
                },
                {
                    'name': 'favorites',
                    'options': {
                        'primaryKey': 'user_id',
                        'indexedFields': ['user_id']
                    }
                },
                {
                    'name': 'file_records',
                    'options': {
                        'primaryKey': 'id',
                        'indexedFields': ['user_id', 'filename']
                    }
                },
                {
                    'name': 'feedback',
                    'options': {
                        'primaryKey': 'id',
                        'indexedFields': ['user_id', 'status', 'created_at']
                    }
                }
            ]

            for coll in collections_to_create:
                logger.info(f"创建MongoDB集合: {coll['name']}")
                result = mongo_store.create_collection(coll['name'], coll['options'])
                if result['status'] == 'error' and 'already exists' in result.get('message', ''):
                    logger.info(f"集合 {coll['name']} 已存在")
                elif result['status'] == 'error':
                    logger.warning(f"创建集合 {coll['name']} 失败: {result.get('message')}")
                else:
                    logger.info(f"集合 {coll['name']} 创建成功")

            # 关闭连接
            mongo_store.close()

            # 恢复原始存储类型
            if original_store_type:
                app.config['DOCUMENT_STORE_TYPE'] = original_store_type

            logger.info("MongoDB初始化完成")
        except Exception as e:
            logger.error(f"MongoDB初始化失败: {e}")
            if original_store_type:
                app.config['DOCUMENT_STORE_TYPE'] = original_store_type

def check_mongodb_status(args):
    """检查MongoDB状态"""
    app = import_app()

    with app.app_context():
        try:
            # 检查是否配置了MongoDB
            if app.config.get('DOCUMENT_STORE_TYPE') != 'mongodb':
                logger.info("当前文档存储类型不是MongoDB，将临时切换")
                original_store_type = app.config.get('DOCUMENT_STORE_TYPE')
                app.config['DOCUMENT_STORE_TYPE'] = 'mongodb'
            else:
                original_store_type = None

            # 获取MongoDB存储实例
            from zchat.storage.factory import StorageFactory
            mongo_config = {
                'host': app.config.get('MONGODB_HOST', 'localhost'),
                'port': int(app.config.get('MONGODB_PORT', 27017)),
                'username': app.config.get('MONGODB_USER'),
                'password': app.config.get('MONGODB_PASSWORD'),
                'db_name': app.config.get('MONGODB_DB', 'zchat'),
                'auth_source': app.config.get('MONGODB_AUTH_SOURCE', 'admin')
            }
            mongo_store = StorageFactory.create_store('mongodb', **mongo_config)

            # 获取集合列表
            collections = mongo_store.list_collections()

            print("=== MongoDB状态 ===")
            print(f"MongoDB连接: {mongo_config['host']}:{mongo_config['port']}")
            print(f"数据库: {mongo_config['db_name']}")

            if 'collections' in collections and collections['collections']:
                print(f"集合数量: {len(collections['collections'])}")
                for coll in collections['collections']:
                    # 尝试获取集合中的文档数量
                    db = mongo_store._get_db()
                    doc_count = db[coll['name']].count_documents({})
                    print(f"  - {coll['name']} (主键: {coll['primaryKey']}, 文档数: {doc_count})")
            else:
                print("没有找到集合，数据库可能为空")

            # 关闭连接
            mongo_store.close()

            # 恢复原始存储类型
            if original_store_type:
                app.config['DOCUMENT_STORE_TYPE'] = original_store_type

        except Exception as e:
            print(f"检查MongoDB状态失败: {e}")
            if original_store_type:
                app.config['DOCUMENT_STORE_TYPE'] = original_store_type

def backup_mongodb(args):
    """备份MongoDB数据库"""
    start_time = time.time()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_DIR / f"mongodb_backup_{timestamp}"
    backup_dir.mkdir(exist_ok=True)

    archive_path = BACKUP_DIR / f"mongodb_backup_{timestamp}.gz"

    try:
        # 从应用获取MongoDB配置
        logger.info("开始MongoDB备份过程...")
        app = import_app()

        # MongoDB连接信息
        host = app.config.get('MONGODB_HOST', 'localhost')
        port = app.config.get('MONGODB_PORT', 27017)
        user = app.config.get('MONGODB_USER')
        password = app.config.get('MONGODB_PASSWORD')
        db_name = app.config.get('MONGODB_DB', 'zchat')
        auth_source = app.config.get('MONGODB_AUTH_SOURCE', 'admin')

        logger.info(f"MongoDB连接信息: {host}:{port}, 数据库: {db_name}")

        # 构建备份命令
        cmd = [
            "mongodump",
            f"--host={host}",
            f"--port={port}",
            f"--db={db_name}",
            f"--out={backup_dir}"
        ]

        # 如果提供了认证信息，添加到命令中
        if user and password:
            cmd.extend([
                f"--username={user}",
                f"--password={password}",
                f"--authenticationDatabase={auth_source}"
            ])

        logger.info("执行MongoDB导出命令...")

        # 创建进度显示函数
        def show_progress():
            pbar = tqdm(total=100, desc="MongoDB备份进度", unit="%")
            last_size = 0

            while True:
                # 检查备份目录大小
                if not backup_dir.exists():
                    time.sleep(0.5)
                    continue

                # 计算目录总大小
                total_size = sum(f.stat().st_size for f in backup_dir.glob('**/*') if f.is_file())

                if total_size > last_size:
                    # 更新进度，假设每次变化代表一定比例的进度
                    increment = min(5, 100 - pbar.n)
                    pbar.update(increment)
                    last_size = total_size

                    # 定期记录日志
                    if pbar.n % 20 == 0:
                        logger.info(f"MongoDB备份进行中... ({pbar.n}% 完成，当前大小: {total_size/1024/1024:.2f} MB)")

                if pbar.n >= 100:
                    break

                time.sleep(1)

            pbar.close()

        # 启动进度线程
        progress_thread = threading.Thread(target=show_progress)
        progress_thread.daemon = True
        progress_thread.start()

        # 执行备份命令
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )

        # 处理输出
        for line in process.stdout:
            if line.strip():
                logger.info(f"mongodump: {line.strip()}")

        for line in process.stderr:
            if line.strip():
                logger.warning(f"mongodump error: {line.strip()}")

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mongodump 进程退出，错误码: {exit_code}")

        # 等待进度线程完成
        if progress_thread.is_alive():
            time.sleep(2)

        # 创建归档文件
        logger.info("创建MongoDB备份归档...")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_dir.name)

        # 清理临时目录
        shutil.rmtree(backup_dir)

        # 计算总用时
        elapsed_time = time.time() - start_time
        final_size = archive_path.stat().st_size / (1024 * 1024)  # 转换为MB
        logger.info(f"MongoDB备份已创建: {archive_path} (大小: {final_size:.2f} MB, 用时: {elapsed_time:.2f} 秒)")

        return str(archive_path)
    except Exception as e:
        logger.error(f"MongoDB备份失败: {e}")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if archive_path.exists():
            archive_path.unlink()
        return None

def restore_mongodb(args):
    """恢复MongoDB数据库"""
    start_time = time.time()

    if not args.file:
        logger.error("需要指定MongoDB备份文件 (--file)")
        return False

    backup_file = Path(args.file)
    if not backup_file.exists():
        logger.error(f"备份文件不存在: {backup_file}")
        return False

    # 创建临时目录解压备份
    temp_dir = BACKUP_DIR / "temp_mongodb_restore"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    try:
        logger.info(f"开始从 {backup_file} 恢复MongoDB数据库...")

        # 解压备份文件
        logger.info("解压备份文件...")
        with tarfile.open(backup_file, "r:gz") as tar:
            tar.extractall(path=temp_dir)

        # 查找解压后的备份目录
        backup_dirs = [d for d in temp_dir.iterdir() if d.is_dir() and d.name.startswith("mongodb_backup_")]
        if not backup_dirs:
            logger.error("备份文件格式错误: 未找到MongoDB备份目录")
            return False

        mongodump_dir = backup_dirs[0]
        logger.info(f"找到MongoDB备份目录: {mongodump_dir}")

        # 从应用获取MongoDB配置
        app = import_app()

        # MongoDB连接信息
        host = app.config.get('MONGODB_HOST', 'localhost')
        port = app.config.get('MONGODB_PORT', 27017)
        user = app.config.get('MONGODB_USER')
        password = app.config.get('MONGODB_PASSWORD')
        db_name = app.config.get('MONGODB_DB', 'zchat')
        auth_source = app.config.get('MONGODB_AUTH_SOURCE', 'admin')

        # 构建恢复命令
        cmd = [
            "mongorestore",
            f"--host={host}",
            f"--port={port}",
            f"--db={db_name}",
            "--drop"  # 恢复前删除现有集合
        ]

        # 如果提供了认证信息，添加到命令中
        if user and password:
            cmd.extend([
                f"--username={user}",
                f"--password={password}",
                f"--authenticationDatabase={auth_source}"
            ])

        # 添加备份目录路径
        cmd.append(str(mongodump_dir / db_name))

        logger.info("执行MongoDB恢复命令...")

        # 执行恢复命令
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )

        # 处理输出
        for line in process.stdout:
            if line.strip():
                logger.info(f"mongorestore: {line.strip()}")

        for line in process.stderr:
            if line.strip():
                logger.warning(f"mongorestore error: {line.strip()}")

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mongorestore 进程退出，错误码: {exit_code}")

        # 清理临时目录
        shutil.rmtree(temp_dir)

        # 计算总用时
        elapsed_time = time.time() - start_time
        logger.info(f"MongoDB数据已从 {backup_file} 恢复 (用时: {elapsed_time:.2f} 秒)")
        return True
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"MongoDB恢复失败: {e} (用时: {elapsed_time:.2f} 秒)")
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

    logger.info("所有数据库初始化完成")

def check_all_status(args):
    """检查所有数据库状态"""
    # 设置环境
    setup_env()

    # 检查MySQL
    check_mysql_status(args)
    print("\n")

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

    init_mongodb_parser = subparsers.add_parser("init-mongodb", help="初始化MongoDB")

    # 状态命令
    status_parser = subparsers.add_parser("status", help="检查所有数据库状态")

    mysql_status_parser = subparsers.add_parser("mysql-status", help="检查MySQL状态")

    mongodb_status_parser = subparsers.add_parser("mongodb-status", help="检查MongoDB状态")

    # 迁移管理命令
    reset_migrations_parser = subparsers.add_parser("reset-migrations", help="重置数据库迁移（谨慎使用）")
    reset_migrations_parser.add_argument("--force", action="store_true", help="不提示确认")

    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="创建完整备份")
    backup_parser.add_argument("--description", help="备份描述")
    backup_parser.add_argument("--cleanup", action="store_true", help="清理旧备份")
    backup_parser.add_argument("--keep", type=int, default=5, help="保留的备份数量")

    backup_mysql_parser = subparsers.add_parser("backup-mysql", help="备份MySQL数据库")

    backup_mongodb_parser = subparsers.add_parser("backup-mongodb", help="备份MongoDB")

    # 恢复命令
    restore_parser = subparsers.add_parser("restore", help="从备份恢复")
    restore_parser.add_argument("--file", help="备份文件路径")
    restore_parser.add_argument("--latest", action="store_true", help="使用最新备份")

    restore_mysql_parser = subparsers.add_parser("restore-mysql", help="恢复MySQL数据库")
    restore_mysql_parser.add_argument("--file", required=True, help="MySQL备份文件")

    restore_mongodb_parser = subparsers.add_parser("restore-mongodb", help="恢复MongoDB")
    restore_mongodb_parser.add_argument("--file", required=True, help="MongoDB备份文件")

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
    elif args.command == "init-mongodb":
        init_mongodb(args)
    elif args.command == "init-search":
        init_search(args)
    elif args.command == "status":
        check_all_status(args)
    elif args.command == "mysql-status":
        check_mysql_status(args)
    elif args.command == "mongodb-status":
        check_mongodb_status(args)
    elif args.command == "search-status":
        check_search_status(args)
    elif args.command == "reset-migrations":
        reset_mysql_migrations(args)
    elif args.command == "backup":
        create_full_backup(args)
    elif args.command == "backup-mysql":
        backup_mysql(args)
    elif args.command == "backup-mongodb":
        backup_mongodb(args)
    elif args.command == "restore":
        restore_full_backup(args)
    elif args.command == "restore-mysql":
        restore_mysql(args)
    elif args.command == "restore-mongodb":
        restore_mongodb(args)
    elif args.command == "fix":
        fix_database(args)
    elif args.command == "validate":
        validate_database(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()