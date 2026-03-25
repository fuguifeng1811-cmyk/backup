"""
环境变量构建模块
负责构建备份作业的环境变量配置
"""

import os
from typing import Dict, List


def build_env_vars(backup_config: Dict) -> List[Dict]:
    """
    构建环境变量列表

    Args:
        backup_config: 备份配置

    Returns:
        环境变量列表
    """
    env = []
    params = backup_config.get('parameters', {})
    app_type = backup_config['app_type']

    # 通用环境变量
    if backup_config.get('backup_method'):
        env.append({'name': 'BACKUP_METHOD', 'value': backup_config['backup_method']})

    if backup_config.get('retention_days'):
        env.append({'name': 'RETENTION_DAYS', 'value': str(backup_config['retention_days'])})

    # 应用特定环境变量
    if app_type == 'mysql':
        if params.get('host'):
            env.append({'name': 'MYSQL_HOST', 'value': params['host']})
        if params.get('port'):
            env.append({'name': 'MYSQL_PORT', 'value': params['port']})
        if params.get('user'):
            env.append({'name': 'MYSQL_USER', 'value': params['user']})
        if params.get('database'):
            env.append({'name': 'MYSQL_DATABASE', 'value': params['database']})
        if params.get('dump_options'):
            env.append({'name': 'MYSQLDUMP_OPTIONS', 'value': params['dump_options']})

    elif app_type == 'postgresql':
        if params.get('host'):
            env.append({'name': 'PGHOST', 'value': params['host']})
        if params.get('port'):
            env.append({'name': 'PGPORT', 'value': params['port']})
        if params.get('user'):
            env.append({'name': 'PGUSER', 'value': params['user']})
        if params.get('database'):
            env.append({'name': 'PGDATABASE', 'value': params['database']})
        if params.get('format'):
            env.append({'name': 'BACKUP_FORMAT', 'value': params['format']})

    elif app_type == 'redis':
        if params.get('host'):
            env.append({'name': 'REDIS_HOST', 'value': params['host']})
        if params.get('port'):
            env.append({'name': 'REDIS_PORT', 'value': params['port']})
        if params.get('backup_type'):
            env.append({'name': 'BACKUP_TYPE', 'value': params['backup_type']})

    elif app_type == 'minio':
        if params.get('endpoint'):
            env.append({'name': 'MINIO_ENDPOINT', 'value': params['endpoint']})
        if params.get('bucket'):
            env.append({'name': 'MINIO_BUCKET', 'value': params['bucket']})

    elif app_type == 'generic':
        if params.get('source_path'):
            env.append({'name': 'SOURCE_DIR', 'value': params['source_path']})
        if params.get('backup_method'):
            env.append({'name': 'BACKUP_METHOD', 'value': params['backup_method']})
        if params.get('exclude_patterns'):
            env.append({'name': 'EXCLUDE_PATTERNS', 'value': params['exclude_patterns']})

    # 添加通用备份目录
    env.append({'name': 'BACKUP_DIR', 'value': '/backup'})

    # 添加远程存储环境变量（如果配置了远程存储）
    remote_storage = backup_config.get('remote_storage', {})
    if remote_storage.get('enabled', False):
        env.append({'name': 'REMOTE_STORAGE_ENABLED', 'value': 'true'})
        storage_type = remote_storage.get('type', 'none')
        env.append({'name': 'REMOTE_STORAGE_TYPE', 'value': storage_type})

        if storage_type == 's3':
            s3_config = remote_storage.get('s3', {})
            endpoint = s3_config.get('endpoint', '')
            bucket = s3_config.get('bucket', '')

            if endpoint:
                env.append({'name': 'S3_ENDPOINT', 'value': endpoint})
            if bucket:
                env.append({'name': 'S3_BUCKET', 'value': bucket})

            # S3 访问凭证通过 Secret 引用
            env.extend([
                {
                    'name': 'S3_ACCESS_KEY',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': f"{backup_config['app_name']}-backup-secret",
                            'key': 'S3_ACCESS_KEY'
                        }
                    }
                },
                {
                    'name': 'S3_SECRET_KEY',
                    'valueFrom': {
                        'secretKeyRef': {
                            'name': f"{backup_config['app_name']}-backup-secret",
                            'key': 'S3_SECRET_KEY'
                        }
                    }
                }
            ])

    # 敏感信息从 Secret 引用
    if app_type == 'mysql':
        env.append({
            'name': 'MYSQL_PASSWORD',
            'valueFrom': {
                'secretKeyRef': {
                    'name': f"{backup_config['app_name']}-backup-secret",
                    'key': 'MYSQL_PASSWORD'
                }
            }
        })
    elif app_type == 'postgresql':
        env.append({
            'name': 'PGPASSWORD',
            'valueFrom': {
                'secretKeyRef': {
                    'name': f"{backup_config['app_name']}-backup-secret",
                    'key': 'PGPASSWORD'
                }
            }
        })
    elif app_type == 'redis':
        env.append({
            'name': 'REDIS_PASSWORD',
            'valueFrom': {
                'secretKeyRef': {
                    'name': f"{backup_config['app_name']}-backup-secret",
                    'key': 'REDIS_PASSWORD'
                }
            }
        })
    elif app_type == 'minio':
        env.append({
            'name': 'MINIO_ACCESS_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': f"{backup_config['app_name']}-backup-secret",
                    'key': 'MINIO_ACCESS_KEY'
                }
            }
        })
        env.append({
            'name': 'MINIO_SECRET_KEY',
            'valueFrom': {
                'secretKeyRef': {
                    'name': f"{backup_config['app_name']}-backup-secret",
                    'key': 'MINIO_SECRET_KEY'
                }
            }
        })

    return env