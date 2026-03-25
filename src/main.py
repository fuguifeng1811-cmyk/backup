"""
K8s Backup Manager - 主程序入口

功能:
- 应用发现
- 配置提取
- 备份任务生成
- 备份执行
"""

import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import List, Dict

# 导入模块
from discovery import ApplicationDiscovery
from extractor import ConfigExtractor
from renderer import TemplateRenderer
from utils import load_config, setup_logging, write_file

logger = logging.getLogger(__name__)


class BackupManager:
    """备份管理器"""

    def __init__(self, config_file: str = 'config.yaml'):
        """
        初始化备份管理器

        Args:
            config_file: 配置文件路径
        """
        self.config = load_config(config_file)
        self.discovery = ApplicationDiscovery(
            kubeconfig=self.config.get('kubernetes', {}).get('kubeconfig'),
            context=self.config.get('kubernetes', {}).get('context')
        )
        self.extractor = ConfigExtractor()
        self.renderer = TemplateRenderer()

    def discover(self, namespaces: List[str] = None) -> List[Dict]:
        """
        发现有状态应用

        Args:
            namespaces: 要扫描的命名空间列表，None 则扫描所有

        Returns:
            应用列表
        """
        logger.info("开始发现有状态应用...")
        apps = self.discovery.discover_stateful_apps(namespaces)
        logger.info(f"发现 {len(apps)} 个有状态应用")
        return apps

    def extract_configs(self, apps: List[Dict]) -> List[Dict]:
        """
        提取备份配置

        Args:
            apps: 应用列表

        Returns:
            备份配置列表
        """
        logger.info("开始提取备份配置...")
        backup_configs = []

        for app in apps:
            try:
                backup_config = self.extractor.extract_from_app(app)
                errors = self.extractor.validate_backup_config(backup_config)

                if errors:
                    logger.warning(f"应用 {app['name']} 配置有问题: {', '.join(errors)}")
                    backup_config['valid'] = False
                    backup_config['errors'] = errors
                else:
                    backup_config['valid'] = True

                backup_configs.append(backup_config)
            except Exception as e:
                logger.error(f"提取应用 {app['name']} 配置失败: {e}")

        valid_count = sum(1 for cfg in backup_configs if cfg.get('valid', False))
        logger.info(f"成功提取 {valid_count}/{len(backup_configs)} 个有效备份配置")

        return backup_configs

    def generate_manifests(self, backup_configs: List[Dict], output_dir: str = 'manifests') -> None:
        """
        生成备份清单文件

        Args:
            backup_configs: 备份配置列表
            output_dir: 输出目录
        """
        logger.info(f"开始生成备份清单到目录: {output_dir}")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        generated_count = 0

        for config in backup_configs:
            if not config.get('valid', False):
                logger.warning(f"跳过无效配置: {config['app_name']}")
                continue

            try:
                # 生成完整清单
                manifest = self.renderer.render_backup_manifest(config)

                # 生成文件名
                filename = f"{config['app_name']}-{config['namespace']}-backup.yaml"
                filepath = Path(output_dir) / filename

                # 写入文件
                if write_file(str(filepath), manifest):
                    logger.info(f"已生成: {filename}")
                    generated_count += 1
                else:
                    logger.error(f"写入文件失败: {filename}")

            except Exception as e:
                logger.error(f"生成 {config['app_name']} 清单失败: {e}")

        logger.info(f"成功生成 {generated_count} 个备份清单")

    def discover_and_generate(self, namespaces: List[str] = None, output_dir: str = 'manifests') -> None:
        """
        发现应用并生成备份清单

        Args:
            namespaces: 要扫描的命名空间列表
            output_dir: 输出目录
        """
        # 1. 发现应用
        apps = self.discover(namespaces)

        if not apps:
            logger.warning("未发现任何有状态应用")
            return

        # 2. 提取配置
        backup_configs = self.extract_configs(apps)

        # 3. 生成清单
        self.generate_manifests(backup_configs, output_dir)

        logger.info("✓ 完成: 发现应用并生成备份清单")

    def print_discovery_results(self, apps: List[Dict]) -> None:
        """
        打印发现结果

        Args:
            apps: 应用列表
        """
        if not apps:
            print("未发现任何有状态应用")
            return

        print("\n" + "=" * 80)
        print(f"发现 {len(apps)} 个有状态应用")
        print("=" * 80)

        for app in apps:
            print(f"\n应用名称: {app['name']}")
            print(f"  类型: {app['type']}")
            print(f"  命名空间: {app['namespace']}")
            print(f"  副本数: {app.get('replicas', 'N/A')}")
            print(f"  标签: {app.get('labels', {})}")
            print(f"  使用 PVC: {'是' if app.get('has_pvc') else '否'}")

            if app.get('has_pvc'):
                if app['type'] == 'StatefulSet':
                    pvcs = app.get('pvc_templates', [])
                    print(f"  PVC 模板 ({len(pvcs)} 个):")
                    for pvc in pvcs:
                        print(f"    - {pvc['name']}: {pvc.get('size', 'N/A')} ({pvc.get('storage_class', 'N/A')})")
                else:
                    pvcs = app.get('pvcs', [])
                    print(f"  PVC ({len(pvcs)} 个):")
                    for pvc in pvcs:
                        print(f"    - {pvc['name']}")

        print("\n" + "=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='K8s Backup Manager - Kubernetes 应用备份管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 发现有状态应用
  python main.py discover

  # 发现特定命名空间的应用
  python main.py discover --namespace default --namespace app-prod

  # 发现并生成备份清单
  python main.py generate --output manifests/

  # 使用自定义配置文件
  python main.py discover --config my-config.yaml
        """
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )

    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='日志级别 (默认: INFO)'
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # discover 命令
    discover_parser = subparsers.add_parser('discover', help='发现有状态应用')
    discover_parser.add_argument(
        '--namespace',
        '-n',
        action='append',
        help='要扫描的命名空间（可多次指定），不指定则扫描所有'
    )

    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='发现应用并生成备份清单')
    generate_parser.add_argument(
        '--namespace',
        '-n',
        action='append',
        help='要扫描的命名空间（可多次指定），不指定则扫描所有'
    )
    generate_parser.add_argument(
        '--output',
        '-o',
        default='manifests',
        help='输出目录 (默认: manifests)'
    )

    # extract 命令
    extract_parser = subparsers.add_parser('extract', help='提取备份配置')
    extract_parser.add_argument(
        '--namespace',
        '-n',
        action='append',
        help='要扫描的命名空间（可多次指定），不指定则扫描所有'
    )

    # 渲染测试命令
    render_parser = subparsers.add_parser('render-test', help='测试渲染功能')
    render_parser.add_argument('--quiet', action='store_true', help='静默模式')

    args = parser.parse_args()

    # 配置日志
    log_config = {}
    if Path(args.config).exists():
        config = load_config(args.config)
        log_config = config.get('logging', {})

    setup_logging(
        log_level=args.log_level,
        log_file=log_config.get('file')
    )

    # 没有命令则显示帮助
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        manager = BackupManager(config_file=args.config)

        if args.command == 'discover':
            apps = manager.discover(args.namespace)
            manager.print_discovery_results(apps)

        elif args.command == 'extract':
            apps = manager.discover(args.namespace)
            configs = manager.extract_configs(apps)
            print("\n" + "=" * 80)
            print("提取的备份配置:")
            print("=" * 80)
            print(yaml.dump(configs, default_flow_style=False, allow_unicode=True))

        elif args.command == 'generate':
            manager.discover_and_generate(args.namespace, args.output)

        elif args.command == 'render-test':
            # 测试渲染功能
            test_config = {
                'enabled': True,
                'app_name': 'test-mysql',
                'app_type': 'mysql',
                'namespace': 'test',
                'backup_method': 'mysqldump',
                'schedule': '0 2 * * *',
                'retention_days': 7,
                'parameters': {
                    'host': 'test-mysql.test.svc.cluster.local',
                    'port': '3306',
                    'user': 'backup',
                    'database': 'test_db'
                }
            }
            manifest = manager.renderer.render_backup_manifest(test_config)
            print(manifest)

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
