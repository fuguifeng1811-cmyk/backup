"""
重试机制单元测试
"""

import pytest
import logging
from unittest.mock import Mock, patch
from kubernetes.client.exceptions import ApiException
import boto3.exceptions

# 导入重试装饰器
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.retry import (
    retry_on_k8s_api_error,
    retry_on_s3_error,
    retry_on_network_error,
    retry_with_custom_exceptions,
    RetryConfig
)


class TestRetryDecorators:
    """测试重试装饰器"""

    def test_retry_on_k8s_api_error_success(self):
        """测试 K8s API 重试成功场景"""
        call_count = 0

        @retry_on_k8s_api_error(max_attempts=3, min_wait=0, max_wait=0)
        def mock_k8s_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ApiException(status=500, reason="Internal Server Error")
            return "success"

        result = mock_k8s_call()
        assert result == "success"
        assert call_count == 2  # 第一次失败，第二次成功

    def test_retry_on_k8s_api_error_max_attempts(self):
        """测试 K8s API 重试达到最大次数"""
        call_count = 0

        @retry_on_k8s_api_error(max_attempts=3, min_wait=0, max_wait=0)
        def mock_k8s_call():
            nonlocal call_count
            call_count += 1
            raise ApiException(status=500, reason="Internal Server Error")

        with pytest.raises(ApiException):
            mock_k8s_call()

        assert call_count == 3  # 重试 3 次后失败

    def test_retry_on_s3_error_success(self):
        """测试 S3 API 重试成功场景"""
        call_count = 0

        @retry_on_s3_error(max_attempts=3, min_wait=0, max_wait=0)
        def mock_s3_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise boto3.exceptions.Boto3Error("Connection timeout")
            return "uploaded"

        result = mock_s3_call()
        assert result == "uploaded"
        assert call_count == 2

    def test_retry_on_network_error(self):
        """测试网络错误重试"""
        call_count = 0

        @retry_on_network_error(max_attempts=3, min_wait=0, max_wait=0)
        def mock_network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network unreachable")
            return "connected"

        result = mock_network_call()
        assert result == "connected"
        assert call_count == 3

    def test_retry_with_custom_exceptions(self):
        """测试自定义异常重试"""
        call_count = 0

        @retry_with_custom_exceptions((ValueError, KeyError), max_attempts=3, min_wait=0, max_wait=0)
        def mock_custom_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Invalid value")
            return "valid"

        result = mock_custom_call()
        assert result == "valid"
        assert call_count == 2

    def test_retry_does_not_catch_other_exceptions(self):
        """测试重试不捕获其他异常"""
        @retry_on_k8s_api_error(max_attempts=3, min_wait=0, max_wait=0)
        def mock_call():
            raise RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError):
            mock_call()


class TestRetryConfig:
    """测试重试配置类"""

    def test_retry_config_init(self):
        """测试重试配置初始化"""
        config = RetryConfig(max_attempts=5, min_wait=2, max_wait=20)
        assert config.max_attempts == 5
        assert config.min_wait == 2
        assert config.max_wait == 20

    def test_retry_config_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            'max_attempts': 5,
            'min_wait': 2,
            'max_wait': 20
        }
        config = RetryConfig.from_dict(config_dict)
        assert config.max_attempts == 5
        assert config.min_wait == 2
        assert config.max_wait == 20

    def test_retry_config_from_dict_with_defaults(self):
        """测试从字典创建配置（使用默认值）"""
        config_dict = {}
        config = RetryConfig.from_dict(config_dict)
        assert config.max_attempts == 3  # 默认值
        assert config.min_wait == 1
        assert config.max_wait == 10

    def test_retry_config_to_dict(self):
        """测试配置转换为字典"""
        config = RetryConfig(max_attempts=5, min_wait=2, max_wait=20)
        config_dict = config.to_dict()
        assert config_dict == {
            'max_attempts': 5,
            'min_wait': 2,
            'max_wait': 20
        }


class TestRetryLogging:
    """测试重试日志"""

    def test_retry_logs_warning_before_sleep(self, caplog):
        """测试重试前记录警告日志"""
        caplog.set_level(logging.WARNING)

        @retry_on_k8s_api_error(max_attempts=2, min_wait=0, max_wait=0)
        def mock_call():
            raise ApiException(status=500, reason="Internal Server Error")

        with pytest.raises(ApiException):
            mock_call()

        # 检查是否记录了重试日志
        assert len(caplog.records) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
