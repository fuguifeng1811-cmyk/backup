"""
模板渲染模块 - 生成备份脚本或配置

功能:
- 生成 Kubernetes Job/CronJob YAML
- 生成备份脚本
- 生成 RBAC 配置
"""

import logging
from typing import Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """模板渲染器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def render_backup_job(self, backup_config: Dict) -> str:
        """
        渲染备份 Job YAML

        Args:
            backup_config: 备份配置字典

        Returns:
            Job YAML 字符串
        """
        app_name = backup_config['app_name']
        namespace = backup_config['namespace']
        app_type = backup_config['app_type']
        params = backup_config.get('parameters', {})
        timestamp = backup_config.get('timestamp', 'latest')

        job_name = f"{app_name}-backup-{timestamp}"

        # 根据应用类型选择镜像和命令
        container_spec = self._get_container_spec(app_type, backup_config)

        job_spec = {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {
                'name': job_name,
                'namespace': namespace,
                'labels': {
                    'app': app_name,
                    'backup-type': backup_config.get('backup_method', 'manual'),
                    'app-type': app_type
                },
                'annotations': {
                    'backup.k8s.io/app-name': app_name,
                    'backup.k8s.io/app-type': app_type
                }
            },
            'spec': {
                'template': {
                    'metadata': {
                        'labels': {
                            'app': app_name,
                            'job-name': job_name
                        }
                    },
                    'spec': {
                        'restartPolicy': 'Never',
                        'serviceAccountName': backup_config.get('service_account', 'backup-sa'),
                        'containers': [container_spec]
                    }
                },
                'backoffLimit': 3
            }
        }

        return yaml.dump(job_spec, default_flow_style=False, allow_unicode=True)

    def render_backup_cronjob(self, backup_config: Dict) -> str:
        """
        渲染备份 CronJob YAML

        Args:
            backup_config: 备份配置字典

        Returns:
            CronJob YAML 字符串
        """
        app_name = backup_config['app_name']
        namespace = backup_config['namespace']
        app_type = backup_config['app_type']
        schedule = backup_config.get('schedule', '0 2 * * *')
        params = backup_config.get('parameters', {})

        cronjob_name = f"{app_name}-backup"

        # 根据应用类型选择镜像和命令
        container_spec = self._get_container_spec(app_type, backup_config)

        cronjob_spec = {
            'apiVersion': 'batch/v1',
            'kind': 'CronJob',
            'metadata': {
                'name': cronjob_name,
                'namespace': namespace,
                'labels': {
                    'app': app_name,
                    'backup-type': backup_config.get('backup_method', 'scheduled'),
                    'app-type': app_type
                },
                'annotations': {
                    'backup.k8s.io/app-name': app_name,
                    'backup.k8s.io/app-type': app_type,
                    'backup.k8s.io/schedule': schedule
                }
            },
            'spec': {
                'schedule': schedule,
                'concurrencyPolicy': 'Forbid',
                'successfulJobsHistoryLimit': backup_config.get('successful_jobs_history_limit', 3),
                'failedJobsHistoryLimit': backup_config.get('failed_jobs_history_limit', 1),
                'jobTemplate': {
                    'spec': {
                        'template': {
                            'metadata': {
                                'labels': {
                                    'app': app_name,
                                    'job-name': f"{cronjob_name}-job"
                                }
                            },
                            'spec': {
                                'restartPolicy': 'Never',
                                'serviceAccountName': backup_config.get('service_account', 'backup-sa'),
                                'containers': [container_spec]
                            }
                        }
                    }
                }
            }
        }

        return yaml.dump(cronjob_spec, default_flow_style=False, allow_unicode=True)

    def _get_container_spec(self, app_type: str, backup_config: Dict) -> Dict:
        """
        获取容器规格

        Args:
            app_type: 应用类型
            backup_config: 备份配置

        Returns:
            容器规格字典
        """
        params = backup_config.get('parameters', {})
        method = backup_config.get('backup_method', 'pvc')

        # 镜像选择
        image_map = {
            'mysql': 'mysql:8.0',
            'postgresql': 'postgres:15',
            'redis': 'redis:7-alpine',
            'minio': 'minio/mc:latest',
            'generic': 'alpine:latest'
        }

        image = params.get('image', image_map.get(app_type, 'alpine:latest'))

        # 脚本下载命令
        script_url_base = 'https://raw.githubusercontent.com/your-repo/backup/master/scripts'
        script_map = {
            'mysql': 'mysql-backup.sh',
            'postgresql': 'postgresql-backup.sh',
            'redis': 'redis-backup.sh',
            'minio': 'minio-backup.sh',
            'generic': 'pvc-backup.sh'
        }

        script_name = script_map.get(app_type, 'pvc-backup.sh')
        script_url = f"{script_url_base}/{script_name}"

        # 环境变量
        env = self._build_env_vars(backup_config)

        # 卷挂载
        volume_mounts = self._build_volume_mounts(backup_config)

        # 卷
        volumes = self._build_volumes(backup_config)

        container_spec = {
            'name': 'backup',
            'image': image,
            'imagePullPolicy': backup_config.get('image_pull_policy', 'IfNotPresent'),
            'command': ['/bin/sh', '-c'],
            'args': [
                self._build_backup_command(app_type, method, script_url, script_name)
            ],
            'env': env,
            'volumeMounts': volume_mounts
        }

        # 移除空的字段
        if not volumes:
            container_spec['volumes'] = volumes

        return container_spec

    def _build_backup_command(self, app_type: str, method: str, script_url: str, script_name: str) -> str:
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
        commands = []

        # 安装必要的工具（对于 alpine 镜像）
        if 'alpine' in script_name:
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

        # 下载脚本
        commands.append(f"curl -sSL -o /tmp/{script_name} {script_url}")
        commands.append(f"chmod +x /tmp/{script_name}")

        # 设置备份类型
        if app_type == 'mysql':
            backup_type = 'full' if method == 'mysqldump' else 'binlog'
            commands.append(f"BACKUP_TYPE={backup_type} /tmp/{script_name}")
        elif app_type == 'redis':
            backup_type = params.get('backup_type', 'rdb')
            commands.append(f"BACKUP_TYPE={backup_type} /tmp/{script_name}")
        else:
            commands.append(f"/tmp/{script_name}")

        return ' && '.join(commands)

    def _build_env_vars(self, backup_config: Dict) -> List[Dict]:
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

    def _build_volume_mounts(self, backup_config: Dict) -> List[Dict]:
        """
        构建卷挂载列表

        Args:
            backup_config: 备份配置

        Returns:
            卷挂载列表
        """
        volume_mounts = []
        app_type = backup_config['app_type']
        params = backup_config.get('parameters', {})

        # 备份存储卷
        volume_mounts.append({
            'name': 'backup-storage',
            'mountPath': '/backup'
        })

        # 应用数据卷（只读）
        if app_type == 'generic' and backup_config.get('has_pvc'):
            volume_mounts.append({
                'name': 'app-data',
                'mountPath': params.get('source_path', '/data'),
                'readOnly': True
            })

        return volume_mounts

    def _build_volumes(self, backup_config: Dict) -> List[Dict]:
        """
        构建卷列表

        Args:
            backup_config: 备份配置

        Returns:
            卷列表
        """
        volumes = []

        # 备份存储卷
        volumes.append({
            'name': 'backup-storage',
            'persistentVolumeClaim': {
                'claimName': f"{backup_config['app_name']}-backup-pvc"
            }
        })

        # 应用数据卷
        if backup_config.get('has_pvc'):
            volumes.append({
                'name': 'app-data',
                'persistentVolumeClaim': {
                    'claimName': backup_config.get('pvc_name', f"{backup_config['app_name']}-data")
                }
            })

        return volumes

    def render_backup_secret(self, backup_config: Dict) -> Optional[str]:
        """
        渲染备份 Secret YAML

        Args:
            backup_config: 备份配置字典

        Returns:
            Secret YAML 字符串或 None
        """
        app_name = backup_config['app_name']
        namespace = backup_config['namespace']
        app_type = backup_config['app_type']
        params = backup_config.get('parameters', {})

        secret_data = {}

        if app_type == 'mysql':
            secret_data['MYSQL_PASSWORD'] = 'your-password'  # 用户需要修改
        elif app_type == 'postgresql':
            secret_data['PGPASSWORD'] = 'your-password'
        elif app_type == 'redis':
            secret_data['REDIS_PASSWORD'] = 'your-password'
        elif app_type == 'minio':
            secret_data['MINIO_ACCESS_KEY'] = 'your-access-key'
            secret_data['MINIO_SECRET_KEY'] = 'your-secret-key'

        if not secret_data:
            return None

        secret_spec = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': f"{app_name}-backup-secret",
                'namespace': namespace,
                'annotations': {
                    'backup.k8s.io/app-name': app_name
                }
            },
            'type': 'Opaque',
            'stringData': secret_data
        }

        return yaml.dump(secret_spec, default_flow_style=False, allow_unicode=True)

    def render_backup_pvc(self, backup_config: Dict) -> str:
        """
        渲染备份 PVC YAML

        Args:
            backup_config: 备份配置字典

        Returns:
            PVC YAML 字符串
        """
        app_name = backup_config['app_name']
        namespace = backup_config['namespace']
        storage_size = backup_config.get('backup_storage_size', '100Gi')
        storage_class = backup_config.get('storage_class', 'standard')

        pvc_spec = {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {
                'name': f"{app_name}-backup-pvc",
                'namespace': namespace,
                'annotations': {
                    'backup.k8s.io/app-name': app_name
                }
            },
            'spec': {
                'accessModes': ['ReadWriteOnce'],
                'resources': {
                    'requests': {
                        'storage': storage_size
                    }
                },
                'storageClassName': storage_class
            }
        }

        return yaml.dump(pvc_spec, default_flow_style=False, allow_unicode=True)

    def render_backup_rbac(self, namespace: str = 'default') -> str:
        """
        渲染备份 RBAC 配置

        Args:
            namespace: 命名空间

        Returns:
            RBAC YAML 字符串（包含 ServiceAccount、Role、RoleBinding）
        """
        rbac_specs = []

        # ServiceAccount
        sa_spec = {
            'apiVersion': 'v1',
            'kind': 'ServiceAccount',
            'metadata': {
                'name': 'backup-sa',
                'namespace': namespace
            }
        }
        rbac_specs.append(sa_spec)

        # Role
        role_spec = {
            'apiVersion': 'rbac.authorization.k8s.io/v1',
            'kind': 'Role',
            'metadata': {
                'name': 'backup-role',
                'namespace': namespace
            },
            'rules': [
                {
                    'apiGroups': [''],
                    'resources': ['pods', 'pods/exec'],
                    'verbs': ['get', 'list', 'create']
                },
                {
                    'apiGroups': [''],
                    'resources': ['persistentvolumeclaims'],
                    'verbs': ['get', 'list', 'create']
                },
                {
                    'apiGroups': ['snapshot.storage.k8s.io'],
                    'resources': ['volumesnapshots'],
                    'verbs': ['get', 'list', 'create', 'delete']
                }
            ]
        }
        rbac_specs.append(role_spec)

        # RoleBinding
        rolebinding_spec = {
            'apiVersion': 'rbac.authorization.k8s.io/v1',
            'kind': 'RoleBinding',
            'metadata': {
                'name': 'backup-role-binding',
                'namespace': namespace
            },
            'subjects': [
                {
                    'kind': 'ServiceAccount',
                    'name': 'backup-sa',
                    'namespace': namespace
                }
            ],
            'roleRef': {
                'kind': 'Role',
                'name': 'backup-role',
                'apiGroup': 'rbac.authorization.k8s.io'
            }
        }
        rbac_specs.append(rolebinding_spec)

        return '---\n'.join([yaml.dump(spec, default_flow_style=False, allow_unicode=True) for spec in rbac_specs])

    def render_backup_manifest(self, backup_config: Dict) -> str:
        """
        渲染完整的备份清单（包含所有资源）

        Args:
            backup_config: 备份配置字典

        Returns:
            完整的 YAML 清单字符串
        """
        resources = []

        # RBAC
        resources.append(self.render_backup_rbac(backup_config['namespace']))

        # Secret
        secret_yaml = self.render_backup_secret(backup_config)
        if secret_yaml:
            resources.append(secret_yaml)

        # PVC
        resources.append(self.render_backup_pvc(backup_config))

        # CronJob
        resources.append(self.render_backup_cronjob(backup_config))

        return '---\n'.join(resources)


# 使用示例
if __name__ == "__main__":
    renderer = TemplateRenderer()

    # 示例备份配置
    backup_config = {
        'enabled': True,
        'app_name': 'mysql-primary',
        'app_type': 'mysql',
        'namespace': 'database',
        'resource_type': 'StatefulSet',
        'backup_method': 'mysqldump',
        'schedule': '0 2 * * *',
        'retention_days': 7,
        'storage_class': 'ceph-block',
        'backup_storage_size': '500Gi',
        'service_account': 'backup-sa',
        'has_pvc': True,
        'parameters': {
            'host': 'mysql-primary-0.mysql-primary.database.svc.cluster.local',
            'port': '3306',
            'user': 'backup',
            'database': 'app_db',
            'dump_options': '--single-transaction --quick'
        }
    }

    print("=" * 60)
    print("生成的 CronJob YAML:")
    print("=" * 60)
    cronjob_yaml = renderer.render_backup_cronjob(backup_config)
    print(cronjob_yaml)

    print("=" * 60)
    print("生成的 Secret YAML:")
    print("=" * 60)
    secret_yaml = renderer.render_backup_secret(backup_config)
    print(secret_yaml)

    print("=" * 60)
    print("生成的 PVC YAML:")
    print("=" * 60)
    pvc_yaml = renderer.render_backup_pvc(backup_config)
    print(pvc_yaml)

    print("=" * 60)
    print("生成的完整清单:")
    print("=" * 60)
    manifest_yaml = renderer.render_backup_manifest(backup_config)
    print(manifest_yaml)
