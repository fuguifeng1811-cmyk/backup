"""
卷配置构建模块
负责构建备份作业的卷挂载和卷配置
"""

from typing import Dict, List


def build_volume_mounts(backup_config: Dict) -> List[Dict]:
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

    # 检查是否启用离线模式
    offline_mode = backup_config.get('offline_mode', False)

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

    # 如果启用离线模式，添加脚本卷挂载
    if offline_mode:
        volume_mounts.append({
            'name': 'backup-scripts',
            'mountPath': '/scripts',
            'readOnly': True
        })

    return volume_mounts


def build_volumes(backup_config: Dict) -> List[Dict]:
    """
    构建卷列表

    Args:
        backup_config: 备份配置

    Returns:
        卷列表
    """
    volumes = []

    # 检查是否启用离线模式
    offline_mode = backup_config.get('offline_mode', False)

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

    # 如果启用离线模式，添加脚本卷
    if offline_mode:
        volumes.append({
            'name': 'backup-scripts',
            'configMap': {
                'name': f"{backup_config['app_name']}-backup-scripts",
                'defaultMode': 0o755  # 确保脚本具有可执行权限
            }
        })

    return volumes