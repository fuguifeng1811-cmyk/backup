"""
命令构建模块
负责构建备份作业的命令和参数
"""

import os
from typing import Dict, Any, Union


def build_backup_command(app_type: str, method: str, script_url: str, script_name: str) -> str:
    """
    构建备份命令

    Args:
        app_type: 应用类型
        method: 备份方法
        script_url: 脚本 URL
        script_name: 脚本名称

    Returns:
        备份命令字符串
    """
    commands: list[str] = []

    # 检查是否使用离线模式（从ConfigMap挂载脚本）
    offline_mode = os.environ.get('OFFLINE_MODE', 'false').lower() == 'true'

    # 安装必要的工具（对于 alpine 镜像）
    if 'alpine' in script_name and not offline_mode:
        tools = []
        if app_type == 'generic':
            if method == 'rsync':
                tools.append('rsync')
            elif method == 'tar':
                tools.extend(['tar', 'gzip'])
        elif app_type == 'minio':
            tools.append('curl')

        if tools:
            commands.append(f"apk add --no-cache {' '.join(tools)}")

    if offline_mode:
        # 离线模式：使用从ConfigMap挂载的脚本
        script_path = f"/scripts/{script_name}"
        commands.append(f"chmod +x {script_path}")

        # 设置环境变量并执行备份
        if app_type == 'mysql':
            backup_type = 'full' if method == 'mysqldump' else 'binlog'
            commands.append(f"APP_TYPE=mysql BACKUP_TYPE={backup_type} {script_path}")
        elif app_type == 'redis':
            commands.append(f"APP_TYPE=redis BACKUP_TYPE=rdb {script_path}")
        elif app_type == 'minio':
            commands.append(f"APP_TYPE=minio {script_path}")
        elif app_type == 'postgresql':
            commands.append(f"APP_TYPE=postgresql {script_path}")
        else:
            commands.append(f"APP_TYPE=generic {script_path}")
    else:
        # 在线模式：下载脚本
        # 下载主要备份脚本
        commands.append(f"curl -sSL -o /tmp/{script_name} {script_url}")
        commands.append(f"chmod +x /tmp/{script_name}")

        # 如果有远程存储支持，也需要下载远程上传脚本
        remote_upload_script = "remote-upload.sh"
        remote_upload_url = f"https://raw.githubusercontent.com/your-repo/backup/master/scripts/{remote_upload_script}"
        commands.append(f"curl -sSL -o /tmp/{remote_upload_script} {remote_upload_url}")
        commands.append(f"chmod +x /tmp/{remote_upload_script}")

        # 如果启用了备份验证，下载验证脚本
        verify_enabled = os.environ.get('BACKUP_VERIFY_ENABLED', 'false').lower() == 'true'
        if verify_enabled:
            verify_script = "backup-verify.sh"
            verify_url = f"https://raw.githubusercontent.com/your-repo/backup/master/scripts/{verify_script}"
            commands.append(f"curl -sSL -o /tmp/{verify_script} {verify_url}")
            commands.append(f"chmod +x /tmp/{verify_script}")

        # 设置环境变量并执行备份
        if app_type == 'mysql':
            backup_type = 'full' if method == 'mysqldump' else 'binlog'
            commands.append(f"APP_TYPE=mysql BACKUP_TYPE={backup_type} /tmp/{script_name}")
        elif app_type == 'redis':
            commands.append(f"APP_TYPE=redis BACKUP_TYPE=rdb /tmp/{script_name}")
        elif app_type == 'minio':
            commands.append(f"APP_TYPE=minio /tmp/{script_name}")
        elif app_type == 'postgresql':
            commands.append(f"APP_TYPE=postgresql /tmp/{script_name}")
        else:
            commands.append(f"APP_TYPE=generic /tmp/{script_name}")

        # 如果启用了备份验证，在上传前验证备份
        if verify_enabled:
            commands.append(f"APP_TYPE={app_type} /tmp/{verify_script}")

        # 如果启用了远程存储，执行远程上传
        commands.append(f"/tmp/{remote_upload_script}")

    return ' && '.join(commands)