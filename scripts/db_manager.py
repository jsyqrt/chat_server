#!/usr/bin/env python3
"""
简化版数据库备份与恢复工具

这个脚本提供了统一的命令行界面，用于管理数据库的备份和恢复：
- MySQL数据库的备份和恢复
- MongoDB文档存储的备份和恢复
- 全量数据库备份和恢复

常见问题解答(FAQ):

Q: 我的MySQL备份恢复过程卡住了但没有报错，可能是什么原因？
A: 最常见的原因是表元数据锁冲突。当恢复进程尝试修改表结构(如DROP TABLE)时，
   如果有其他连接正在使用或持有这些表的锁，恢复过程会卡住等待锁释放。

   解决方法:
   1. 使用 "SHOW PROCESSLIST;" 检查当前所有数据库连接
   2. 寻找状态为 "Waiting for table metadata lock" 的进程，确认是恢复操作
   3. 终止所有空闲(Sleep)状态的连接: "KILL [connection_id];"
   4. 如果有应用程序正在运行，临时停止它们以避免新的连接干扰恢复过程
   5. 对于重复出现此问题的环境，考虑增大 innodb_lock_wait_timeout 参数值

   注意：这种情况在开发或测试环境尤为常见，因为可能有多个连接同时打开且长时间不活动

Q: 什么规模的数据库可以使用这个脚本进行备份和恢复？
A: 此脚本适用于小型到中型数据库(几MB到几GB)。对于更大规模的数据库，可能需要:
   1. 针对大型数据库优化的备份策略(如增量备份)
   2. 考虑分表或分区策略
   3. 使用专业备份工具如Percona XtraBackup(MySQL)或MongoDB Cloud Manager

   恢复大型数据库时也可能面临更多资源限制和锁争用问题。
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
from tqdm import tqdm
import threading

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
BACKUP_DIR.mkdir(exist_ok=True, parents=True)

def setup_env():
    """设置环境并添加项目路径"""
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault('FLASK_APP', 'zchat')

def import_app():
    """导入应用并创建实例"""
    try:
        from zchat import create_app

        # 设置基本配置（从docker-compose.yml中获取）
        os.environ.setdefault('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://zchat:zchat_password@mysql:3306/zchat')
        os.environ.setdefault('DOCUMENT_STORE_TYPE', 'mongodb')

        # 创建应用实例，使用工具模式跳过不必要的蓝图和组件
        app = create_app(tool_mode=True)
        logger.info("应用导入成功 (工具模式)")
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

def check_tool_available(tool_name):
    """检查指定的命令行工具是否可用"""
    try:
        subprocess.run(["which", tool_name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

# ========== MySQL备份和恢复函数 ==========

def backup_mysql(args):
    """备份MySQL数据库"""
    # 检查必要工具
    if not check_tool_available("mysqldump"):
        logger.error("MySQL备份工具(mysqldump)不可用。请安装MySQL客户端工具。")
        return None

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

        # 直接执行并将输出重定向到文件和终端
        with open(backup_file, 'w') as f:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                bufsize=1
            )

            # 读取输出并同时写入文件和日志
            for line in process.stdout:
                f.write(line)
                f.flush()
                # 只记录关键消息到日志
                if "Dumping" in line or "error" in line.lower() or "warning" in line.lower():
                    logger.info(line.strip())

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mysqldump 进程退出，错误码: {exit_code}")

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

def restore_mysql(args):
    """恢复MySQL数据库"""
    # 检查必要工具
    if not check_tool_available("mysql"):
        logger.error("MySQL恢复工具(mysql)不可用。请安装MySQL客户端工具。")
        return False

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

        logger.info("执行MySQL恢复命令...")

        # 执行恢复命令并直接显示输出
        with open(backup_file, 'r') as f:
            process = subprocess.Popen(
                cmd,
                stdin=f,
                stdout=sys.stdout,
                stderr=sys.stderr,
                text=True
            )

        # 等待进程完成
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

# ========== MongoDB备份和恢复函数 ==========

def backup_mongodb(args):
    """备份MongoDB数据库"""
    # 检查必要工具
    if not check_tool_available("mongodump"):
        logger.error("MongoDB备份工具(mongodump)不可用。请安装MongoDB数据库工具。")
        return None

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
        host = app.config.get('MONGODB_HOST', 'mongodb')
        port = app.config.get('MONGODB_PORT', 27017)
        user = app.config.get('MONGODB_USER', 'zchat')
        password = app.config.get('MONGODB_PASSWORD', 'zchat_password')
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

        # 执行备份命令并直接显示输出
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mongodump 进程退出，错误码: {exit_code}")

        # 创建归档文件
        logger.info("创建MongoDB备份归档...")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_dir.name)
            logger.info(f"已归档 {backup_dir.name} 到 {archive_path}")

        # 清理临时目录
        shutil.rmtree(backup_dir)
        logger.info(f"已删除临时目录 {backup_dir}")

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
    # 检查必要工具
    if not check_tool_available("mongorestore"):
        logger.error("MongoDB恢复工具(mongorestore)不可用。请安装MongoDB数据库工具。")
        return False

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
            for member in tar.getmembers():
                if member.isfile():
                    logger.info(f"已解压: {member.name}")

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
        host = app.config.get('MONGODB_HOST', 'mongodb')
        port = app.config.get('MONGODB_PORT', 27017)
        user = app.config.get('MONGODB_USER', 'zchat')
        password = app.config.get('MONGODB_PASSWORD', 'zchat_password')
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

        # 执行恢复命令并直接显示输出
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )

        # 等待进程完成
        exit_code = process.wait()

        if exit_code != 0:
            raise Exception(f"mongorestore 进程退出，错误码: {exit_code}")

        # 清理临时目录
        shutil.rmtree(temp_dir)
        logger.info(f"已删除临时目录 {temp_dir}")

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

# ========== 全量备份和恢复函数 ==========

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
            "backup_version": "1.2"
        }

        with open(temp_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
            logger.info("元数据文件已创建")

        # 创建tar归档
        logger.info("第4步: 创建tar归档...")
        archive_path = BACKUP_DIR / f"{backup_name}.tar.gz"

        # 直接创建归档，不显示进度条
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(str(temp_dir), arcname=backup_name)
            logger.info(f"已添加目录 {temp_dir} 到归档")

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
        if hasattr(args, 'cleanup') and args.cleanup:
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

def restore_full_backup(args):
    """恢复完整备份"""
    start_time = time.time()

    if not args.file or args.latest:
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
        with tarfile.open(backup_file, "r:gz") as tar:
            members = tar.getmembers()
            logger.info(f"备份文件包含 {len(members)} 个文件")

            # 解压所有文件，显示进度
            tar.extractall(path=temp_dir)
            logger.info("备份文件解压完成")

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
        if 'temp_dir' in locals() and temp_dir.exists():
            shutil.rmtree(temp_dir)
        return False

# ========== 命令行界面 ==========

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(
        description="数据库备份与恢复工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

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

    # 添加检查命令
    check_parser = subparsers.add_parser("check-tools", help="检查备份恢复工具是否可用")

    # 解析参数
    args = parser.parse_args()

    # 设置环境
    setup_env()

    # 处理命令
    if args.command == "backup":
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
    elif args.command == "check-tools":
        # 检查所有工具是否可用
        print("检查数据库工具是否可用:")
        tools = {
            "MySQL备份工具 (mysqldump)": check_tool_available("mysqldump"),
            "MySQL恢复工具 (mysql)": check_tool_available("mysql"),
            "MongoDB备份工具 (mongodump)": check_tool_available("mongodump"),
            "MongoDB恢复工具 (mongorestore)": check_tool_available("mongorestore")
        }

        all_available = True
        for tool, available in tools.items():
            status = "✅ 可用" if available else "❌ 不可用"
            print(f"{tool}: {status}")
            if not available:
                all_available = False

        if not all_available:
            print("\n缺失工具安装指南:")
            print("1. MySQL工具: apt-get install default-mysql-client")
            print("2. MongoDB工具: apt-get install mongodb-database-tools")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()