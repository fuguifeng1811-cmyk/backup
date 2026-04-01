"""
Prometheus 监控指标模块

提供备份管理器的监控指标,包括:
- 备份成功/失败计数
- 备份耗时统计
- 应用发现统计
- 存储使用量监控
"""

import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)


class BackupMetrics:
    """备份监控指标"""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        初始化监控指标

        Args:
            registry: Prometheus 注册表,None 则使用默认注册表
        """
        self.registry = registry

        # 备份操作计数器
        self.backup_total = Counter(
            'backup_operations_total',
            'Total number of backup operations',
            ['app_name', 'namespace', 'app_type', 'status'],
            registry=registry
        )

        # 备份耗时直方图
        self.backup_duration = Histogram(
            'backup_duration_seconds',
            'Backup operation duration in seconds',
            ['app_name', 'namespace', 'app_type'],
            buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
            registry=registry
        )

        # 备份文件大小直方图
        self.backup_size = Histogram(
            'backup_size_bytes',
            'Backup file size in bytes',
            ['app_name', 'namespace', 'app_type'],
            buckets=(1e6, 10e6, 100e6, 500e6, 1e9, 5e9, 10e9, 50e9),
            registry=registry
        )

        # 应用发现计数器
        self.apps_discovered = Gauge(
            'apps_discovered_total',
            'Total number of stateful applications discovered',
            ['namespace', 'resource_type'],
            registry=registry
        )

        # 存储使用量
        self.storage_used = Gauge(
            'backup_storage_used_bytes',
            'Total backup storage used in bytes',
            ['storage_type', 'location'],
            registry=registry
        )

        # 重试次数计数器
        self.retry_total = Counter(
            'backup_retry_operations_total',
            'Total number of retry operations',
            ['operation_type', 'error_type'],
            registry=registry
        )

        # 当前正在进行的备份
        self.backups_in_progress = Gauge(
            'backups_in_progress',
            'Number of backups currently in progress',
            ['app_type'],
            registry=registry
        )

        # 最后一次成功备份时间
        self.last_backup_success = Gauge(
            'last_backup_success_timestamp',
            'Timestamp of last successful backup',
            ['app_name', 'namespace'],
            registry=registry
        )

        # 备份验证结果
        self.backup_validation = Counter(
            'backup_validation_total',
            'Total number of backup validations',
            ['app_name', 'namespace', 'validation_type', 'result'],
            registry=registry
        )

        # 系统信息
        self.system_info = Info(
            'backup_manager_info',
            'Backup manager system information',
            registry=registry
        )

        logger.info("Prometheus 监控指标初始化完成")

    def record_backup_success(self, app_name: str, namespace: str, app_type: str, duration: float, size: int):
        """
        记录备份成功

        Args:
            app_name: 应用名称
            namespace: 命名空间
            app_type: 应用类型
            duration: 备份耗时（秒）
            size: 备份文件大小（字节）
        """
        self.backup_total.labels(
            app_name=app_name,
            namespace=namespace,
            app_type=app_type,
            status='success'
        ).inc()

        self.backup_duration.labels(
            app_name=app_name,
            namespace=namespace,
            app_type=app_type
        ).observe(duration)

        self.backup_size.labels(
            app_name=app_name,
            namespace=namespace,
            app_type=app_type
        ).observe(size)

        import time
        self.last_backup_success.labels(
            app_name=app_name,
            namespace=namespace
        ).set(time.time())

        logger.info(f"记录备份成功: {namespace}/{app_name} ({app_type}), 耗时: {duration}s, 大小: {size} bytes")

    def record_backup_failure(self, app_name: str, namespace: str, app_type: str, error_type: str = 'unknown'):
        """
        记录备份失败

        Args:
            app_name: 应用名称
            namespace: 命名空间
            app_type: 应用类型
            error_type: 错误类型
        """
        self.backup_total.labels(
            app_name=app_name,
            namespace=namespace,
            app_type=app_type,
            status='failure'
        ).inc()

        logger.warning(f"记录备份失败: {namespace}/{app_name} ({app_type}), 错误类型: {error_type}")

    def record_apps_discovered(self, namespace: str, resource_type: str, count: int):
        """
        记录发现的应用数量

        Args:
            namespace: 命名空间
            resource_type: 资源类型
            count: 应用数量
        """
        self.apps_discovered.labels(
            namespace=namespace,
            resource_type=resource_type
        ).set(count)

        logger.debug(f"记录应用发现: {namespace}/{resource_type} = {count}")

    def record_storage_usage(self, storage_type: str, location: str, bytes_used: int):
        """
        记录存储使用量

        Args:
            storage_type: 存储类型 (local/s3/minio)
            location: 存储位置
            bytes_used: 使用的字节数
        """
        self.storage_used.labels(
            storage_type=storage_type,
            location=location
        ).set(bytes_used)

        logger.debug(f"记录存储使用: {storage_type}/{location} = {bytes_used} bytes")

    def record_retry(self, operation_type: str, error_type: str):
        """
        记录重试操作

        Args:
            operation_type: 操作类型 (k8s_api/s3_upload/network)
            error_type: 错误类型
        """
        self.retry_total.labels(
            operation_type=operation_type,
            error_type=error_type
        ).inc()

        logger.debug(f"记录重试: {operation_type}/{error_type}")

    def backup_started(self, app_type: str):
        """
        记录备份开始

        Args:
            app_type: 应用类型
        """
        self.backups_in_progress.labels(app_type=app_type).inc()

    def backup_finished(self, app_type: str):
        """
        记录备份结束

        Args:
            app_type: 应用类型
        """
        self.backups_in_progress.labels(app_type=app_type).dec()

    def record_validation(self, app_name: str, namespace: str, validation_type: str, result: str):
        """
        记录备份验证结果

        Args:
            app_name: 应用名称
            namespace: 命名空间
            validation_type: 验证类型 (checksum/content/integrity)
            result: 验证结果 (success/failure)
        """
        self.backup_validation.labels(
            app_name=app_name,
            namespace=namespace,
            validation_type=validation_type,
            result=result
        ).inc()

        logger.debug(f"记录验证结果: {namespace}/{app_name} {validation_type} = {result}")

    def set_system_info(self, version: str, python_version: str, k8s_version: str):
        """
        设置系统信息

        Args:
            version: 备份管理器版本
            python_version: Python 版本
            k8s_version: Kubernetes 版本
        """
        self.system_info.info({
            'version': version,
            'python_version': python_version,
            'k8s_version': k8s_version
        })

        logger.info(f"设置系统信息: version={version}, python={python_version}, k8s={k8s_version}")

    def get_metrics(self) -> bytes:
        """
        获取 Prometheus 格式的指标

        Returns:
            指标数据（字节）
        """
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """
        获取指标内容类型

        Returns:
            内容类型
        """
        return CONTENT_TYPE_LATEST


# 全局指标实例
_metrics_instance: Optional[BackupMetrics] = None


def get_metrics() -> BackupMetrics:
    """
    获取全局指标实例

    Returns:
        BackupMetrics 实例
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = BackupMetrics()
    return _metrics_instance


def init_metrics(registry: Optional[CollectorRegistry] = None) -> BackupMetrics:
    """
    初始化全局指标实例

    Args:
        registry: Prometheus 注册表

    Returns:
        BackupMetrics 实例
    """
    global _metrics_instance
    _metrics_instance = BackupMetrics(registry=registry)
    return _metrics_instance


# 使用示例
if __name__ == "__main__":
    import time

    # 初始化指标
    metrics = BackupMetrics()

    # 设置系统信息
    metrics.set_system_info(
        version='0.1.0',
        python_version='3.9.0',
        k8s_version='1.28.0'
    )

    # 模拟备份操作
    print("模拟备份操作...")
    metrics.backup_started('mysql')

    # 记录应用发现
    metrics.record_apps_discovered('database', 'StatefulSet', 3)

    # 模拟备份成功
    time.sleep(1)
    metrics.record_backup_success(
        app_name='mysql-primary',
        namespace='database',
        app_type='mysql',
        duration=45.5,
        size=1024 * 1024 * 100  # 100MB
    )

    metrics.backup_finished('mysql')

    # 记录验证
    metrics.record_validation(
        app_name='mysql-primary',
        namespace='database',
        validation_type='checksum',
        result='success'
    )

    # 记录存储使用
    metrics.record_storage_usage(
        storage_type='local',
        location='/data/backup',
        bytes_used=1024 * 1024 * 1024 * 10  # 10GB
    )

    # 输出指标
    print("\n=== Prometheus 指标 ===")
    print(metrics.get_metrics().decode('utf-8'))
