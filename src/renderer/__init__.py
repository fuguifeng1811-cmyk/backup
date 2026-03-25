"""
模板渲染模块 - 生成备份脚本或配置

功能:
- 生成 Kubernetes Job/CronJob YAML
- 生成备份脚本
- 生成 RBAC 配置
"""

import logging
import os
from typing import Dict, List, Optional
import yaml

from .env_builder import build_env_vars
from .volume_builder import build_volume_mounts, build_volumes
from .command_builder import build_backup_command

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
        env = build_env_vars(backup_config)

        # 卷挂载
        volume_mounts = build_volume_mounts(backup_config)

        # 卷
        volumes = build_volumes(backup_config)

        container_spec = {
            'name': 'backup',
            'image': image,
            'imagePullPolicy': backup_config.get('image_pull_policy', 'IfNotPresent'),
            'command': ['/bin/sh', '-c'],
            'args': [
                build_backup_command(app_type, method, script_url, script_name)
            ],
            'env': env,
            'volumeMounts': volume_mounts
        }

        # 移除空的字段
        if not volumes:
            container_spec['volumes'] = volumes

        return container_spec

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
            secret_data['MYSQL_PASSWORD'] = 'CHANGE_ME'  # TODO: Replace with actual password from user input or external secret
        elif app_type == 'postgresql':
            secret_data['PGPASSWORD'] = 'CHANGE_ME'
        elif app_type == 'redis':
            secret_data['REDIS_PASSWORD'] = 'CHANGE_ME'
        elif app_type == 'minio':
            secret_data['MINIO_ACCESS_KEY'] = 'CHANGE_ME'
            secret_data['MINIO_SECRET_KEY'] = 'CHANGE_ME'

        # 添加 S3 存储凭证（如果配置了远程存储）
        remote_storage = backup_config.get('remote_storage', {})
        if remote_storage.get('enabled', False):
            storage_type = remote_storage.get('type', 'none')
            if storage_type == 's3':
                secret_data['S3_ACCESS_KEY'] = 'CHANGE_ME'
                secret_data['S3_SECRET_KEY'] = 'CHANGE_ME'

        if not secret_data:
            return None

        secret_spec = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {
                'name': f"{app_name}-backup-secret",
                'namespace': namespace,
                'annotations': {
                    'backup.k8s.io/app-name': app_name,
                    'kubernetes.io/description': 'Backup credentials - update with actual secrets before use'
                }
            },
            'type': 'Opaque',
            'stringData': secret_data
        }

        # Add warning comment at the top
        warning_comment = """# WARNING: This Secret contains placeholder values
# Replace all 'CHANGE_ME' values with actual secrets before applying
# Example: kubectl create secret generic {name} --from-literal=MYSQL_PASSWORD='actual-password' -n {namespace}
""".format(name=f"{app_name}-backup-secret", namespace=namespace)

        yaml_output = yaml.dump(secret_spec, default_flow_style=False, allow_unicode=True)
        return warning_comment + yaml_output

    def render_backup_scripts_configmap(self, backup_config: Dict) -> str:
        """
        渲染备份脚本 ConfigMap

        Args:
            backup_config: 备份配置字典

        Returns:
            ConfigMap YAML 字符串
        """

        app_name = backup_config['app_name']
        namespace = backup_config['namespace']
        app_type = backup_config['app_type']

        # 读取脚本内容
        script_files = {}

        # 主备份脚本
        script_map = {
            'mysql': 'mysql-backup.sh',
            'postgresql': 'postgresql-backup.sh',
            'redis': 'redis-backup.sh',
            'minio': 'minio-backup.sh',
            'generic': 'pvc-backup.sh'
        }

        main_script_name = script_map.get(app_type, 'pvc-backup.sh')
        script_path = f"scripts/{main_script_name}"

        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            script_files[main_script_name] = script_content
        except FileNotFoundError:
            # 如果脚本不存在，使用一个占位脚本
            script_files[main_script_name] = f"""#!/bin/bash
# Placeholder script for {app_type}
echo "Placeholder backup script for {app_type}"
echo "This is a placeholder in offline mode"
"""

        # 添加远程上传脚本
        try:
            with open("scripts/remote-upload.sh", 'r', encoding='utf-8') as f:
                remote_upload_content = f.read()
            script_files["remote-upload.sh"] = remote_upload_content
        except FileNotFoundError:
            script_files["remote-upload.sh"] = """#!/bin/bash
# Placeholder remote upload script
echo "Placeholder remote upload script"
"""

        # 添加验证脚本
        try:
            with open("scripts/backup-verify.sh", 'r', encoding='utf-8') as f:
                verify_content = f.read()
            script_files["backup-verify.sh"] = verify_content
        except FileNotFoundError:
            script_files["backup-verify.sh"] = """#!/bin/bash
# Placeholder backup verification script
echo "Placeholder backup verification script"
"""

        configmap_spec = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': f"{app_name}-backup-scripts",
                'namespace': namespace,
                'annotations': {
                    'backup.k8s.io/app-name': app_name,
                    'kubernetes.io/description': 'Backup scripts for offline environments'
                }
            },
            'data': script_files
        }

        return yaml.dump(configmap_spec, default_flow_style=False, allow_unicode=True)

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

        # 如果启用离线模式，添加脚本 ConfigMap
        if backup_config.get('offline_mode', False):
            resources.append(self.render_backup_scripts_configmap(backup_config))

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