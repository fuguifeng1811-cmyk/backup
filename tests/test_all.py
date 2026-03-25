"""
单元测试 - K8s Backup Manager
"""

import unittest
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))


class TestDiscovery(unittest.TestCase):
    """测试应用发现模块"""

    def test_import_discovery(self):
        """测试能否导入 discovery 模块"""
        try:
            from discovery import ApplicationDiscovery
            self.assertIsNotNone(ApplicationDiscovery)
        except Exception as e:
            self.fail(f"导入 discovery 模块失败: {e}")


class TestExtractor(unittest.TestCase):
    """测试配置提取模块"""

    def setUp(self):
        from extractor import ConfigExtractor
        self.extractor = ConfigExtractor()

    def test_extract_from_app(self):
        """测试从应用提取配置"""
        app_info = {
            'type': 'StatefulSet',
            'name': 'mysql-test',
            'namespace': 'test',
            'labels': {'app': 'mysql'},
            'annotations': {
                'backup.k8s.io/app-type': 'mysql',
                'backup.k8s.io/method': 'mysqldump',
                'backup.k8s.io/schedule': '0 2 * * *',
                'backup.k8s.io/mysql-host': 'mysql.test.svc.cluster.local'
            },
            'has_pvc': True
        }

        config = self.extractor.extract_from_app(app_info)

        self.assertTrue(config['enabled'])
        self.assertEqual(config['app_type'], 'mysql')
        self.assertEqual(config['backup_method'], 'mysqldump')
        self.assertEqual(config['parameters']['host'], 'mysql.test.svc.cluster.local')

    def test_detect_app_type(self):
        """测试应用类型检测"""
        # 测试 MySQL
        app1 = {'name': 'mysql-primary', 'labels': {'app': 'mysql'}}
        self.assertEqual(self.extractor._detect_app_type(app1), 'mysql')

        # 测试 PostgreSQL
        app2 = {'name': 'postgres-main', 'labels': {}}
        self.assertEqual(self.extractor._detect_app_type(app2), 'postgresql')

        # 测试 Redis
        app3 = {'name': 'redis-cache', 'labels': {}}
        self.assertEqual(self.extractor._detect_app_type(app3), 'redis')

    def test_extract_annotations(self):
        """测试从注解提取配置"""
        annotations = {
            'backup.k8s.io/enabled': 'true',
            'backup.k8s.io/method': 'snapshot',
            'backup.k8s.io/retention-days': '14',
            'backup.k8s.io/schedule': '0 3 * * *'
        }

        config = self.extractor._extract_from_annotations(annotations)

        self.assertTrue(config['enabled'])
        self.assertEqual(config['backup_method'], 'snapshot')
        self.assertEqual(config['retention_days'], 14)
        self.assertEqual(config['schedule'], '0 3 * * *')


class TestUtils(unittest.TestCase):
    """测试工具函数模块"""

    def test_load_config(self):
        """测试加载配置文件"""
        from utils import load_config

        # 测试加载示例配置
        config = load_config('config.example.yaml')
        self.assertIsNotNone(config)
        self.assertIsInstance(config, dict)

    def test_format_size(self):
        """测试大小格式化"""
        from utils import format_size

        self.assertEqual(format_size('100Gi'), 100 * 1024 ** 3)
        self.assertEqual(format_size('500Mi'), 500 * 1024 ** 2)
        self.assertEqual(format_size('10G'), 10 * 1024 ** 3)
        self.assertEqual(format_size('100'), 100)

    def test_merge_configs(self):
        """测试合并配置"""
        from utils import merge_configs

        base = {'a': 1, 'b': {'c': 2}}
        override = {'b': {'d': 3}, 'e': 4}

        result = merge_configs(base, override)

        self.assertEqual(result['a'], 1)
        self.assertEqual(result['b']['c'], 2)
        self.assertEqual(result['b']['d'], 3)
        self.assertEqual(result['e'], 4)

    def test_is_valid_kubernetes_name(self):
        """测试 Kubernetes 名称验证"""
        from utils import is_valid_kubernetes_name

        self.assertTrue(is_valid_kubernetes_name('test-name'))
        self.assertTrue(is_valid_kubernetes_name('test123'))
        self.assertFalse(is_valid_kubernetes_name('Test-Name'))  # 大写字母
        self.assertFalse(is_valid_kubernetes_name('test name'))  # 空格
        self.assertFalse(is_valid_kubernetes_name('-test'))  # 不能以 - 开头


class TestRenderer(unittest.TestCase):
    """测试模板渲染模块"""

    def setUp(self):
        from renderer import TemplateRenderer
        self.renderer = TemplateRenderer()

    def test_render_backup_cronjob(self):
        """测试渲染 CronJob"""
        backup_config = {
            'enabled': True,
            'app_name': 'test-app',
            'app_type': 'generic',
            'namespace': 'test',
            'backup_method': 'rsync',
            'schedule': '0 2 * * *',
            'retention_days': 7,
            'has_pvc': True
        }

        yaml_output = self.renderer.render_backup_cronjob(backup_config)

        self.assertIn('apiVersion: batch/v1', yaml_output)
        self.assertIn('kind: CronJob', yaml_output)
        self.assertIn('name: test-app-backup', yaml_output)
        self.assertIn('schedule: 0 2 * * *', yaml_output)

    def test_render_backup_pvc(self):
        """测试渲染 PVC"""
        backup_config = {
            'app_name': 'test-app',
            'namespace': 'test',
            'backup_storage_size': '100Gi',
            'storage_class': 'standard'
        }

        yaml_output = self.renderer.render_backup_pvc(backup_config)

        self.assertIn('kind: PersistentVolumeClaim', yaml_output)
        self.assertIn('name: test-app-backup-pvc', yaml_output)
        self.assertIn('storage: 100Gi', yaml_output)

    def test_render_backup_secret(self):
        """测试渲染 Secret"""
        # MySQL Secret
        mysql_config = {
            'app_name': 'mysql-test',
            'app_type': 'mysql',
            'namespace': 'test'
        }

        secret_yaml = self.renderer.render_backup_secret(mysql_config)
        self.assertIn('MYSQL_PASSWORD', secret_yaml)

        # PostgreSQL Secret
        pg_config = {
            'app_name': 'postgres-test',
            'app_type': 'postgresql',
            'namespace': 'test'
        }

        secret_yaml = self.renderer.render_backup_secret(pg_config)
        self.assertIn('PGPASSWORD', secret_yaml)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流程（不连接 Kubernetes）"""
        from extractor import ConfigExtractor
        from renderer import TemplateRenderer

        extractor = ConfigExtractor()
        renderer = TemplateRenderer()

        # 模拟应用发现结果
        app_info = {
            'type': 'StatefulSet',
            'name': 'mysql-test',
            'namespace': 'test',
            'labels': {'app': 'mysql'},
            'annotations': {
                'backup.k8s.io/app-type': 'mysql',
                'backup.k8s.io/method': 'mysqldump',
                'backup.k8s.io/schedule': '0 2 * * *'
            },
            'has_pvc': True
        }

        # 提取配置
        backup_config = extractor.extract_from_app(app_info)
        self.assertTrue(backup_config['enabled'])
        self.assertEqual(backup_config['app_type'], 'mysql')

        # 渲染清单
        manifest = renderer.render_backup_manifest(backup_config)
        self.assertIsNotNone(manifest)
        self.assertIn('CronJob', manifest)
        self.assertIn('Secret', manifest)
        self.assertIn('PersistentVolumeClaim', manifest)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
