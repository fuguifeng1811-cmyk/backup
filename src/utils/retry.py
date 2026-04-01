"""
重试机制工具模块

提供统一的重试装饰器和配置，用于处理 API 调用失败、网络超时等场景
"""

import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from kubernetes.client.exceptions import ApiException
import boto3.exceptions

logger = logging.getLogger(__name__)


# 默认重试配置
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT = 1  # 秒
DEFAULT_MAX_WAIT = 10  # 秒


def retry_on_k8s_api_error(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: int = DEFAULT_MIN_WAIT,
    max_wait: int = DEFAULT_MAX_WAIT
) -> Callable:
    """
    Kubernetes API 调用重试装饰器

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Returns:
        装饰器函数

    Example:
        @retry_on_k8s_api_error(max_attempts=5)
        def list_pods(namespace):
            return core_v1.list_namespaced_pod(namespace)
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type((ApiException, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


def retry_on_s3_error(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: int = DEFAULT_MIN_WAIT,
    max_wait: int = DEFAULT_MAX_WAIT
) -> Callable:
    """
    S3 API 调用重试装饰器

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Returns:
        装饰器函数

    Example:
        @retry_on_s3_error(max_attempts=5)
        def upload_file(file_path, bucket, key):
            s3_client.upload_file(file_path, bucket, key)
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type((
            boto3.exceptions.Boto3Error,
            ConnectionError,
            TimeoutError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


def retry_on_network_error(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: int = DEFAULT_MIN_WAIT,
    max_wait: int = DEFAULT_MAX_WAIT
) -> Callable:
    """
    通用网络错误重试装饰器

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Returns:
        装饰器函数

    Example:
        @retry_on_network_error()
        def fetch_data(url):
            return requests.get(url)
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            OSError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


def retry_with_custom_exceptions(
    exception_types: Tuple[Type[Exception], ...],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: int = DEFAULT_MIN_WAIT,
    max_wait: int = DEFAULT_MAX_WAIT
) -> Callable:
    """
    自定义异常类型重试装饰器

    Args:
        exception_types: 需要重试的异常类型元组
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Returns:
        装饰器函数

    Example:
        @retry_with_custom_exceptions((ValueError, KeyError), max_attempts=5)
        def process_data(data):
            return data['key']
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exception_types),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )


class RetryConfig:
    """重试配置类"""

    def __init__(
        self,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_wait: int = DEFAULT_MIN_WAIT,
        max_wait: int = DEFAULT_MAX_WAIT
    ):
        """
        初始化重试配置

        Args:
            max_attempts: 最大重试次数
            min_wait: 最小等待时间（秒）
            max_wait: 最大等待时间（秒）
        """
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait

    @classmethod
    def from_dict(cls, config: dict) -> 'RetryConfig':
        """
        从字典创建重试配置

        Args:
            config: 配置字典

        Returns:
            RetryConfig 实例
        """
        return cls(
            max_attempts=config.get('max_attempts', DEFAULT_MAX_ATTEMPTS),
            min_wait=config.get('min_wait', DEFAULT_MIN_WAIT),
            max_wait=config.get('max_wait', DEFAULT_MAX_WAIT)
        )

    def to_dict(self) -> dict:
        """
        转换为字典

        Returns:
            配置字典
        """
        return {
            'max_attempts': self.max_attempts,
            'min_wait': self.min_wait,
            'max_wait': self.max_wait
        }


# 使用示例
if __name__ == "__main__":
    import time

    # 示例 1: Kubernetes API 重试
    @retry_on_k8s_api_error(max_attempts=3)
    def test_k8s_api():
        print("尝试调用 K8s API...")
        raise ApiException(status=500, reason="Internal Server Error")

    # 示例 2: S3 API 重试
    @retry_on_s3_error(max_attempts=3)
    def test_s3_api():
        print("尝试调用 S3 API...")
        raise boto3.exceptions.Boto3Error("Connection timeout")

    # 示例 3: 自定义异常重试
    @retry_with_custom_exceptions((ValueError,), max_attempts=3)
    def test_custom():
        print("尝试处理数据...")
        raise ValueError("Invalid data")

    # 运行测试
    try:
        test_k8s_api()
    except Exception as e:
        print(f"K8s API 测试失败: {e}")

    try:
        test_s3_api()
    except Exception as e:
        print(f"S3 API 测试失败: {e}")

    try:
        test_custom()
    except Exception as e:
        print(f"自定义测试失败: {e}")
