# 重试机制配置说明

## 概述

K8s Backup Manager 现已集成自动重试机制,用于处理 API 调用失败、网络超时等临时性错误。重试机制基于 `tenacity` 库实现,支持指数退避策略。

## 功能特性

- ✅ Kubernetes API 调用自动重试
- ✅ S3 兼容存储操作自动重试
- ✅ 网络错误自动重试
- ✅ 可配置的重试次数和等待时间
- ✅ 指数退避策略
- ✅ 详细的重试日志

## 重试策略

### 默认配置

```python
DEFAULT_MAX_ATTEMPTS = 3      # 最大重试次数
DEFAULT_MIN_WAIT = 1          # 最小等待时间（秒）
DEFAULT_MAX_WAIT = 10         # 最大等待时间（秒）
```

### 指数退避

重试等待时间采用指数退避策略:
- 第 1 次重试: 等待 1 秒
- 第 2 次重试: 等待 2 秒
- 第 3 次重试: 等待 4 秒
- 最大等待时间不超过 10 秒

## 使用场景

### 1. Kubernetes API 调用

所有 Kubernetes API 调用已自动应用重试机制:

```python
from utils.retry import retry_on_k8s_api_error

@retry_on_k8s_api_error(max_attempts=3)
def list_pods(namespace):
    return core_v1.list_namespaced_pod(namespace)
```

**已应用的模块**:
- `src/discovery/__init__.py` - 应用发现模块
  - `_discover_statefulsets()`
  - `_discover_pvc_deployments()`
  - `_discover_pvc_daemonsets()`
  - `_discover_pvc_replicasets()`
  - `_discover_pvc_pods()`
  - `_get_all_namespaces()`
  - `get_pvc_details()`

### 2. S3 存储操作

S3 兼容存储操作已自动应用重试机制:

```python
from utils.retry import retry_on_s3_error

@retry_on_s3_error(max_attempts=3)
def upload_file(file_path, bucket, key):
    s3_client.upload_file(file_path, bucket, key)
```

**已应用的模块**:
- `src/storage/s3_handler.py` - S3 存储处理器
  - `upload_file()`
  - `download_file()`
  - `create_bucket_if_not_exists()`

### 3. 自定义重试

如需自定义重试行为:

```python
from utils.retry import retry_with_custom_exceptions

@retry_with_custom_exceptions(
    exception_types=(ValueError, KeyError),
    max_attempts=5,
    min_wait=2,
    max_wait=30
)
def process_data(data):
    return data['key']
```

## 配置文件支持

可以在 `config.yaml` 中配置重试参数:

```yaml
# 重试配置
retry:
  # Kubernetes API 重试
  k8s_api:
    max_attempts: 3
    min_wait: 1
    max_wait: 10

  # S3 存储重试
  s3:
    max_attempts: 5
    min_wait: 2
    max_wait: 30

  # 网络重试
  network:
    max_attempts: 3
    min_wait: 1
    max_wait: 10
```

## 日志输出

重试机制会记录详细的日志:

```
WARNING - Retrying in 1.0 seconds as it raised ApiException: (500) Internal Server Error
WARNING - Retrying in 2.0 seconds as it raised ApiException: (500) Internal Server Error
INFO - Successfully completed after 3 attempts
```

## 错误处理

### 可重试的错误

**Kubernetes API**:
- `ApiException` - API 调用异常
- `ConnectionError` - 连接错误
- `TimeoutError` - 超时错误

**S3 存储**:
- `Boto3Error` - S3 客户端错误
- `ConnectionError` - 连接错误
- `TimeoutError` - 超时错误

**网络**:
- `ConnectionError` - 连接错误
- `TimeoutError` - 超时错误
- `OSError` - 系统错误

### 不可重试的错误

以下错误不会触发重试,会立即失败:
- 认证错误 (401 Unauthorized)
- 权限错误 (403 Forbidden)
- 资源不存在 (404 Not Found)
- 参数错误 (400 Bad Request)
- 其他非临时性错误

## 最佳实践

### 1. 合理设置重试次数

```python
# 快速失败场景 (如健康检查)
@retry_on_k8s_api_error(max_attempts=2, min_wait=0, max_wait=1)
def health_check():
    pass

# 重要操作场景 (如备份上传)
@retry_on_s3_error(max_attempts=5, min_wait=2, max_wait=60)
def upload_backup():
    pass
```

### 2. 监控重试指标

建议监控以下指标:
- 重试次数
- 重试成功率
- 平均重试时间
- 最终失败率

### 3. 避免无限重试

始终设置合理的 `max_attempts`,避免无限重试导致资源耗尽。

### 4. 区分临时性和永久性错误

对于永久性错误 (如配置错误、权限不足),应立即失败而不是重试。

## 测试

运行重试机制测试:

```bash
# 运行所有重试测试
python -m pytest tests/test_retry.py -v

# 运行特定测试
python -m pytest tests/test_retry.py::TestRetryDecorators::test_retry_on_k8s_api_error_success -v
```

## 故障排查

### 问题 1: 重试次数过多

**现象**: 日志中出现大量重试记录

**解决方案**:
1. 检查网络连接
2. 检查 API Server 状态
3. 检查认证配置
4. 适当降低重试次数

### 问题 2: 重试时间过长

**现象**: 操作耗时过长

**解决方案**:
1. 减少 `max_wait` 时间
2. 减少 `max_attempts` 次数
3. 检查是否有永久性错误

### 问题 3: 重试失败

**现象**: 达到最大重试次数后仍然失败

**解决方案**:
1. 检查错误日志确定根本原因
2. 确认是否为永久性错误
3. 检查网络和服务状态
4. 考虑增加重试次数或等待时间

## 相关资源

- [tenacity 文档](https://tenacity.readthedocs.io/)
- [Kubernetes API 错误处理](https://kubernetes.io/docs/reference/using-api/api-concepts/)
- [AWS S3 错误处理](https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html)

## 更新日志

- **2026-04-01**: 添加重试机制支持
  - 实现 `retry.py` 工具模块
  - 在 discovery 模块中应用重试
  - 在 s3_handler 模块中应用重试
  - 添加单元测试
