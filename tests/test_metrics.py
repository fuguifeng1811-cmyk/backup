"""
Prometheus 监控指标单元测试
"""

import pytest
import time
import sys
from pathlib import Path
from prometheus_client import CollectorRegistry

# 导入监控指标模块
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from utils.metrics import BackupMetrics, init_metrics


class TestBackupMetrics:
    """测试监控指标"""

    def setup_method(self):
        """测试前准备:创建私有注册表"""
        self.registry = CollectorRegistry()
        self.metrics = BackupMetrics(registry=self.registry)

    def test_record_backup_success(self):
        """测试记录备份成功"""
        self.metrics.record_backup_success(
            app_name='test-app',
            namespace='test-ns',
            app_type='mysql',
            duration=45.5,
            size=1024 * 1024 * 100  # 100MB
        )

        # 检查指标是否存在
        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_operations_total{app_name="test-app",app_type="mysql",namespace="test-ns",status="success"} 1.0' in metrics_data
        assert 'backup_duration_seconds_bucket{app_name="test-app",app_type="mysql",le="60.0",namespace="test-ns"} 1.0' in metrics_data
        assert 'backup_size_bytes_bucket{app_name="test-app",app_type="mysql",le="104857600.0",namespace="test-ns"} 1.0' in metrics_data
        assert 'last_backup_success_timestamp{app_name="test-app",namespace="test-ns"}' in metrics_data

    def test_record_backup_failure(self):
        """测试记录备份失败"""
        self.metrics.record_backup_failure(
            app_name='test-app',
            namespace='test-ns',
            app_type='mysql',
            error_type='connection_error'
        )

        # 检查指标是否存在
        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_operations_total{app_name="test-app",app_type="mysql",namespace="test-ns",status="failure"} 1.0' in metrics_data

    def test_record_apps_discovered(self):
        """测试记录应用发现"""
        self.metrics.record_apps_discovered(
            namespace='production',
            resource_type='StatefulSet',
            count=5
        )

        # 检查指标是否存在
        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'apps_discovered_total{namespace="production",resource_type="StatefulSet"} 5.0' in metrics_data

    def test_record_storage_usage(self):
        """测试记录存储使用量"""
        self.metrics.record_storage_usage(
            storage_type='s3',
            location='backup-bucket',
            bytes_used=1024 * 1024 * 1024 * 50  # 50GB
        )

        # 检查指标是否存在
        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_storage_used_bytes{location="backup-bucket",storage_type="s3"} 5.36870912e+10' in metrics_data

    def test_record_retry(self):
        """测试记录重试"""
        self.metrics.record_retry(
            operation_type='k8s_api',
            error_type='ApiException'
        )
        self.metrics.record_retry(
            operation_type='k8s_api',
            error_type='ApiException'
        )

        # 检查指标是否存在
        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_retry_operations_total{error_type="ApiException",operation_type="k8s_api"} 2.0' in metrics_data

    def test_backups_in_progress(self):
        """测试正在进行的备份"""
        self.metrics.backup_started('mysql')
        self.metrics.backup_started('mysql')

        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backups_in_progress{app_type="mysql"} 2.0' in metrics_data

        self.metrics.backup_finished('mysql')

        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backups_in_progress{app_type="mysql"} 1.0' in metrics_data

    def test_record_validation(self):
        """测试记录备份验证"""
        self.metrics.record_validation(
            app_name='test-app',
            namespace='test-ns',
            validation_type='checksum',
            result='success'
        )

        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_validation_total{app_name="test-app",namespace="test-ns",result="success",validation_type="checksum"} 1.0' in metrics_data

    def test_set_system_info(self):
        """测试设置系统信息"""
        self.metrics.set_system_info(
            version='0.2.0',
            python_version='3.9.0',
            k8s_version='1.28.0'
        )

        metrics_data = self.metrics.get_metrics().decode('utf-8')
        assert 'backup_manager_info_info{k8s_version="1.28.0",python_version="3.9.0",version="0.2.0"} 1.0' in metrics_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
