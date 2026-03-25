"""
工具函数模块

功能:
- 配置文件加载
- 日志配置
- 常用工具函数
"""

import logging
import yaml
import os
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


def load_config(config_file: str = 'config.yaml') -> Dict:
    """
    加载配置文件

    Args:
        config_file: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 格式错误
    """
    config_path = Path(config_file)

    if not config_path.exists():
        # 尝试加载示例配置
        example_path = Path('config.example.yaml')
        if example_path.exists():
            logger.warning(f"配置文件 {config_file} 不存在，使用示例配置")
            config_path = example_path
        else:
            raise FileNotFoundError(f"配置文件 {config_file} 不存在")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_file}")
            return config or {}
    except yaml.YAMLError as e:
        logger.error(f"配置文件格式错误: {e}")
        raise


def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None) -> None:
    """
    配置日志

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，None 则输出到控制台
    """
    # 转换日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 配置根日志
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 如果指定了日志文件，添加文件处理器
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

        # 添加到根日志
        logging.getLogger().addHandler(file_handler)

    logger.info(f"日志配置完成: level={log_level}, file={log_file}")


def get_env_or_default(key: str, default: Any = None) -> Any:
    """
    从环境变量获取值，如果不存在则返回默认值

    Args:
        key: 环境变量键
        default: 默认值

    Returns:
        环境变量值或默认值
    """
    value = os.environ.get(key)
    if value is None:
        return default

    # 尝试转换为布尔值
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'

    # 尝试转换为数字
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    return value


def merge_configs(base: Dict, override: Dict) -> Dict:
    """
    合并两个配置字典（override 优先级更高）

    Args:
        base: 基础配置
        override: 覆盖配置

    Returns:
        合并后的配置
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


def filter_namespaces(namespaces: list, exclude: list) -> list:
    """
    过滤命名空间列表

    Args:
        namespaces: 命名空间列表
        exclude: 要排除的命名空间列表

    Returns:
        过滤后的命名空间列表
    """
    if not exclude:
        return namespaces

    return [ns for ns in namespaces if ns not in exclude]


def match_pattern(text: str, patterns: list) -> bool:
    """
    检查文本是否匹配任何模式（支持通配符）

    Args:
        text: 要检查的文本
        patterns: 模式列表（支持 * 通配符）

    Returns:
        是否匹配
    """
    import fnmatch

    if not patterns:
        return False

    for pattern in patterns:
        if fnmatch.fnmatch(text, pattern):
            return True

    return False


def format_size(size_str: str) -> int:
    """
    将存储大小字符串转换为字节数

    Args:
        size_str: 大小字符串（如 "100Gi", "500Mi", "10G"）

    Returns:
        字节数

    Example:
        >>> format_size("100Gi")
        107374182400
        >>> format_size("500Mi")
        524288000
    """
    if not size_str:
        return 0

    size_str = size_str.strip().upper()

    # 单位映射
    units = {
        'B': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
        'KI': 1024,
        'MI': 1024 ** 2,
        'GI': 1024 ** 3,
        'TI': 1024 ** 4,
    }

    # 提取数字和单位
    import re
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]I?B?)?$', size_str)
    if not match:
        logger.warning(f"无法解析大小: {size_str}")
        return 0

    number = float(match.group(1))
    unit = match.group(2) or 'B'

    return int(number * units.get(unit.upper(), 1))


def create_directory(path: str) -> bool:
    """
    创建目录（如果不存在）

    Args:
        path: 目录路径

    Returns:
        是否成功
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {path}: {e}")
        return False


def read_file(file_path: str) -> Optional[str]:
    """
    读取文件内容

    Args:
        file_path: 文件路径

    Returns:
        文件内容或 None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
        return None


def write_file(file_path: str, content: str) -> bool:
    """
    写入文件内容

    Args:
        file_path: 文件路径
        content: 文件内容

    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"写入文件失败 {file_path}: {e}")
        return False


def is_valid_kubernetes_name(name: str) -> bool:
    """
    检查是否为有效的 Kubernetes 资源名称

    Args:
        name: 资源名称

    Returns:
        是否有效
    """
    import re

    # Kubernetes 资源名称规则: 小写字母、数字、-，最长 253 字符
    pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'

    if len(name) > 253:
        return False

    return bool(re.match(pattern, name))


def truncate_string(text: str, max_length: int = 63) -> str:
    """
    截断字符串到指定长度（符合 Kubernetes 标签值限制）

    Args:
        text: 字符串
        max_length: 最大长度

    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text

    return text[:max_length]


def generate_backup_filename(app_name: str, namespace: str, backup_type: str) -> str:
    """
    生成备份文件名

    Args:
        app_name: 应用名称
        namespace: 命名空间
        backup_type: 备份类型 (full/incremental)

    Returns:
        备份文件名
    """
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{app_name}_{namespace}_{timestamp}_{backup_type}"


# 使用示例
if __name__ == "__main__":
    # 测试配置加载
    print("=== 测试配置加载 ===")
    try:
        config = load_config('config.example.yaml')
        print(f"配置加载成功: {list(config.keys())}")
    except Exception as e:
        print(f"配置加载失败: {e}")

    # 测试日志配置
    print("\n=== 测试日志配置 ===")
    setup_logging(log_level='INFO')
    logger.info("这是一个测试日志")

    # 测试大小转换
    print("\n=== 测试大小转换 ===")
    print(f"100Gi = {format_size('100Gi')} bytes")
    print(f"500Mi = {format_size('500Mi')} bytes")

    # 测试目录创建
    print("\n=== 测试目录创建 ===")
    if create_directory('/tmp/test_backup'):
        print("目录创建成功")
    else:
        print("目录创建失败")
