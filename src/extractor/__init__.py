"""
配置提取模块 - 从应用配置中提取备份相关信息

功能:
- 从 Kubernetes 资源注解和标签提取备份配置
- 识别应用类型（MySQL、PostgreSQL、Redis 等）
- 提取备份参数（数据库连接信息、备份方式等）
"""

import logging
import re
from typing import Dict, Optional, List
from kubernetes.client import V1ObjectMeta

logger = logging.getLogger(__name__)


class ConfigExtractor:
    """配置提取器"""

    # 应用类型识别规则
    APP_TYPE_PATTERNS = {
        'mysql': [
            r'mysql',
            r'mariadb',
            r'percona'
        ],
        'postgresql': [
            r'postgres',
            r'postgresql',
            r'pg'
        ],
        'redis': [
            r'redis'
        ],
        'mongodb': [
            r'mongo',
            r'mongodb'
        ],
        'minio': [
            r'minio'
        ],
        'elasticsearch': [
            r'elastic',
            r'elasticsearch',
            r'es'
        ]
    }

    # 备份相关的注解前缀
    BACKUP_ANNOTATION_PREFIX = 'backup.k8s.io/'
    BACKUP_LABEL_PREFIX = 'backup-enabled'

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_from_app(self, app: Dict) -> Dict:
        """
        从应用信息中提取备份配置

        Args:
            app: 应用信息字典（来自 discovery 模块）

        Returns:
            备份配置字典
        """
        backup_config = {
            'enabled': True,
            'app_name': app.get('name', ''),
            'app_type': self._detect_app_type(app),
            'namespace': app.get('namespace', ''),
            'resource_type': app.get('type', ''),
            'labels': app.get('labels', {}),
            'annotations': app.get('annotations', {}),
            'backup_method': 'pvc',  # default
            'schedule': None,
            'retention_days': 7,
            'storage_class': None,
            'parameters': {}
        }

        # 从注解提取配置
        annotations = app.get('annotations', {})
        backup_config.update(self._extract_from_annotations(annotations))

        # 从标签提取配置
        labels = app.get('labels', {})
        backup_config.update(self._extract_from_labels(labels))

        # 提取应用特定参数
        app_type = backup_config['app_type']
        if app_type:
            backup_config['parameters'].update(
                self._extract_app_specific_params(app, app_type)
            )

        return backup_config

    def _detect_app_type(self, app: Dict) -> Optional[str]:
        """
        检测应用类型

        Args:
            app: 应用信息字典

        Returns:
            应用类型（mysql/postgresql/redis 等）或 None
        """
        name = app.get('name', '').lower()
        labels = app.get('labels', {})
        annotations = app.get('annotations', {})

        # 1. 检查是否有明确的应用类型注解
        app_type = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}app-type')
        if app_type:
            return app_type.lower()

        # 2. 从名称检测
        for app_type, patterns in self.APP_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    return app_type

        # 3. 从标签检测
        for key, value in labels.items():
            for app_type, patterns in self.APP_TYPE_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, key, re.IGNORECASE) or re.search(pattern, value, re.IGNORECASE):
                        return app_type

        # 4. 如果使用 PVC，至少是通用 PVC 备份
        if app.get('has_pvc'):
            return 'generic'

        return None

    def _extract_from_annotations(self, annotations: Dict) -> Dict:
        """
        从注解中提取备份配置

        支持的注解:
        - backup.k8s.io/enabled: "true"/"false"
        - backup.k8s.io/app-type: "mysql"
        - backup.k8s.io/method: "mysqldump"/"snapshot"/"rsync"
        - backup.k8s.io/schedule: "0 2 * * *"
        - backup.k8s.io/retention-days: "7"
        - backup.k8s.io/storage-class: "ceph-block"
        - backup.k8s.io/exclude-patterns: "*.log,*.tmp"

        Args:
            annotations: 注解字典

        Returns:
            备份配置字典
        """
        config = {}

        # 是否启用备份
        enabled = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}enabled')
        if enabled is not None:
            config['enabled'] = enabled.lower() == 'true'

        # 备份方法
        method = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}method')
        if method:
            config['backup_method'] = method.lower()

        # CronJob 调度
        schedule = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}schedule')
        if schedule:
            config['schedule'] = schedule

        # 保留天数
        retention = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}retention-days')
        if retention:
            try:
                config['retention_days'] = int(retention)
            except ValueError:
                logger.warning(f"无效的保留天数: {retention}")

        # 存储类
        storage_class = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}storage-class')
        if storage_class:
            config['storage_class'] = storage_class

        # 排除模式
        exclude_patterns = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}exclude-patterns')
        if exclude_patterns:
            config['exclude_patterns'] = [p.strip() for p in exclude_patterns.split(',')]

        # 备份前/后钩子脚本
        pre_hook = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}pre-hook')
        if pre_hook:
            config['pre_hook'] = pre_hook

        post_hook = annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}post-hook')
        if post_hook:
            config['post_hook'] = post_hook

        return config

    def _extract_from_labels(self, labels: Dict) -> Dict:
        """
        从标签中提取备份配置

        支持的标签:
        - backup-enabled: "true"/"false"

        Args:
            labels: 标签字典

        Returns:
            备份配置字典
        """
        config = {}

        # 检查是否启用备份
        enabled = labels.get(self.BACKUP_LABEL_PREFIX)
        if enabled is not None:
            config['enabled'] = enabled.lower() == 'true'

        return config

    def _extract_app_specific_params(self, app: Dict, app_type: str) -> Dict:
        """
        提取应用特定的备份参数

        Args:
            app: 应用信息字典
            app_type: 应用类型

        Returns:
            应用特定参数字典
        """
        params = {}

        annotations = app.get('annotations', {})
        labels = app.get('labels', {})
        name = app.get('name', '')

        if app_type == 'mysql':
            params.update({
                'host': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}mysql-host', f'{name}-0.{name}.{app["namespace"]}.svc.cluster.local'),
                'port': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}mysql-port', '3306'),
                'user': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}mysql-user', 'backup'),
                'database': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}mysql-database'),
                'dump_options': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}mysql-dump-options', '--single-transaction --quick --lock-tables=false')
            })

        elif app_type == 'postgresql':
            params.update({
                'host': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}postgres-host', f'{name}-0.{name}.{app["namespace"]}.svc.cluster.local'),
                'port': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}postgres-port', '5432'),
                'user': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}postgres-user', 'backup'),
                'database': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}postgres-database'),
                'format': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}postgres-format', 'custom')
            })

        elif app_type == 'redis':
            params.update({
                'host': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}redis-host', f'{name}.{app["namespace"]}.svc.cluster.local'),
                'port': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}redis-port', '6379'),
                'backup_type': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}redis-backup-type', 'rdb')  # rdb or aof
            })

        elif app_type == 'minio':
            params.update({
                'endpoint': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}minio-endpoint'),
                'bucket': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}minio-bucket'),
                'access_key': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}minio-access-key'),
                'secret_key': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}minio-secret-key')
            })

        elif app_type == 'generic':
            # 通用 PVC 备份
            params.update({
                'source_path': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}source-path', '/data'),
                'backup_method': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}backup-method', 'rsync'),  # rsync, tar, or snapshot
                'include_patterns': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}include-patterns'),
                'exclude_patterns': annotations.get(f'{self.BACKUP_ANNOTATION_PREFIX}exclude-patterns')
            })

        return params

    def extract_from_pod_template(self, pod_template) -> Dict:
        """
        从 Pod 模板中提取备份相关信息

        Args:
            pod_template: Pod 模板对象

        Returns:
            备份配置字典
        """
        config = {}

        # 提取环境变量中的备份相关配置
        if pod_template.spec.containers:
            for container in pod_template.spec.containers:
                if container.env:
                    env_vars = {env.name: env.value for env in container.env if env.value}
                    config['env_vars'] = env_vars

        return config

    def validate_backup_config(self, backup_config: Dict) -> List[str]:
        """
        验证备份配置的有效性

        Args:
            backup_config: 备份配置字典

        Returns:
            错误信息列表（空列表表示配置有效）
        """
        errors = []

        if not backup_config.get('enabled'):
            return errors

        app_type = backup_config.get('app_type')
        if not app_type:
            errors.append("无法确定应用类型")

        method = backup_config.get('backup_method')
        if not method:
            errors.append("未指定备份方法")

        schedule = backup_config.get('schedule')
        if not schedule and backup_config.get('resource_type') in ['StatefulSet', 'Deployment']:
            errors.append("未指定备份调度时间（schedule）")

        # 验证应用特定参数
        params = backup_config.get('parameters', {})
        if app_type == 'mysql':
            if not params.get('host'):
                errors.append("MySQL 备份需要指定 host")
            if not params.get('user'):
                errors.append("MySQL 备份需要指定 user")

        elif app_type == 'postgresql':
            if not params.get('host'):
                errors.append("PostgreSQL 备份需要指定 host")
            if not params.get('user'):
                errors.append("PostgreSQL 备份需要指定 user")

        return errors


# 使用示例
if __name__ == "__main__":
    extractor = ConfigExtractor()

    # 示例应用信息（来自 discovery 模块）
    app_info = {
        'type': 'StatefulSet',
        'name': 'mysql-primary',
        'namespace': 'database',
        'labels': {
            'app': 'mysql',
            'backup-enabled': 'true'
        },
        'annotations': {
            'backup.k8s.io/app-type': 'mysql',
            'backup.k8s.io/method': 'mysqldump',
            'backup.k8s.io/schedule': '0 2 * * *',
            'backup.k8s.io/retention-days': '7',
            'backup.k8s.io/mysql-host': 'mysql-primary-0.mysql-primary.database.svc.cluster.local',
            'backup.k8s.io/mysql-user': 'backup',
            'backup.k8s.io/mysql-database': 'app_db'
        },
        'has_pvc': True
    }

    # 提取备份配置
    backup_config = extractor.extract_from_app(app_info)
    print("提取的备份配置:")
    import json
    print(json.dumps(backup_config, indent=2, ensure_ascii=False))

    # 验证配置
    errors = extractor.validate_backup_config(backup_config)
    if errors:
        print("\n配置错误:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ 配置有效")
