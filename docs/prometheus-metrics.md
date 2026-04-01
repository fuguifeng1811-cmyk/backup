# Prometheus 监控指标说明

## 概述

K8s Backup Manager 集成了 Prometheus 监控指标,用于跟踪备份操作、系统性能和资源使用情况。

## 功能特性

- ✅ 备份成功/失败计数
- ✅ 备份耗时统计
- ✅ 备份文件大小统计
- ✅ 应用发现统计
- ✅ 存储使用量监控
- ✅ 重试操作统计
- ✅ 正在进行的备份数量
- ✅ 最后成功备份时间
- ✅ 备份验证结果统计
- ✅ 系统信息

## 可用指标

### 1. 备份操作计数器

**指标名称**: `backup_operations_total`

**类型**: Counter

**标签**:
- `app_name`: 应用名称
- `namespace`: 命名空间
- `app_type`: 应用类型 (mysql/postgresql/redis/minio/generic)
- `status`: 状态 (success/failure)

**说明**: 记录备份操作的总次数

**示例**:
```
backup_operations_total{app_name="mysql-primary",namespace="database",app_type="mysql",status="success"} 42
backup_operations_total{app_name="mysql-primary",namespace="database",app_type="mysql",status="failure"} 3
```

### 2. 备份耗时直方图

**指标名称**: `backup_duration_seconds`

**类型**: Histogram

**标签**:
- `app_name`: 应用名称
- `namespace`: 命名空间
- `app_type`: 应用类型

**桶**: 10s, 30s, 60s, 120s, 300s, 600s, 1800s, 3600s

**说明**: 记录备份操作的耗时分布

**示例**:
```
backup_duration_seconds_bucket{app_name="mysql-primary",app_type="mysql",le="60.0",namespace="database"} 15
backup_duration_seconds_sum{app_name="mysql-primary",app_type="mysql",namespace="database"} 1234.5
backup_duration_seconds_count{app_name="mysql-primary",app_type="mysql",namespace="database"} 42
```

### 3. 备份文件大小直方图

**指标名称**: `backup_size_bytes`

**类型**: Histogram

**标签**:
- `app_name`: 应用名称
- `namespace`: 命名空间
- `app_type`: 应用类型

**桶**: 1MB, 10MB, 100MB, 500MB, 1GB, 5GB, 10GB, 50GB

**说明**: 记录备份文件大小分布

**示例**:
```
backup_size_bytes_bucket{app_name="mysql-primary",app_type="mysql",le="104857600.0",namespace="database"} 20
backup_size_bytes_sum{app_name="mysql-primary",app_type="mysql",namespace="database"} 5368709120
backup_size_bytes_count{app_name="mysql-primary",app_type="mysql",namespace="database"} 42
```

### 4. 应用发现统计

**指标名称**: `apps_discovered_total`

**类型**: Gauge

**标签**:
- `namespace`: 命名空间
- `resource_type`: 资源类型 (StatefulSet/Deployment/DaemonSet/ReplicaSet/Pod)

**说明**: 记录发现的有状态应用数量

**示例**:
```
apps_discovered_total{namespace="database",resource_type="StatefulSet"} 5
apps_discovered_total{namespace="database",resource_type="Deployment"} 3
```

### 5. 存储使用量

**指标名称**: `backup_storage_used_bytes`

**类型**: Gauge

**标签**:
- `storage_type`: 存储类型 (local/s3/minio/ceph)
- `location`: 存储位置

**说明**: 记录备份存储使用量

**示例**:
```
backup_storage_used_bytes{storage_type="s3",location="backup-bucket"} 53687091200
backup_storage_used_bytes{storage_type="local",location="/data/backup"} 10737418240
```

### 6. 重试操作计数器

**指标名称**: `backup_retry_operations_total`

**类型**: Counter

**标签**:
- `operation_type`: 操作类型 (k8s_api/s3_upload/network)
- `error_type`: 错误类型

**说明**: 记录重试操作的总次数

**示例**:
```
backup_retry_operations_total{operation_type="k8s_api",error_type="ApiException"} 12
backup_retry_operations_total{operation_type="s3_upload",error_type="ConnectionError"} 5
```

### 7. 正在进行的备份

**指标名称**: `backups_in_progress`

**类型**: Gauge

**标签**:
- `app_type`: 应用类型

**说明**: 记录当前正在进行的备份数量

**示例**:
```
backups_in_progress{app_type="mysql"} 2
backups_in_progress{app_type="postgresql"} 1
```

### 8. 最后成功备份时间

**指标名称**: `last_backup_success_timestamp`

**类型**: Gauge

**标签**:
- `app_name`: 应用名称
- `namespace`: 命名空间

**说明**: 记录最后一次成功备份的时间戳

**示例**:
```
last_backup_success_timestamp{app_name="mysql-primary",namespace="database"} 1711958400
```

### 9. 备份验证结果

**指标名称**: `backup_validation_total`

**类型**: Counter

**标签**:
- `app_name`: 应用名称
- `namespace`: 命名空间
- `validation_type`: 验证类型 (checksum/content/integrity)
- `result`: 验证结果 (success/failure)

**说明**: 记录备份验证操作的总次数

**示例**:
```
backup_validation_total{app_name="mysql-primary",namespace="database",validation_type="checksum",result="success"} 40
backup_validation_total{app_name="mysql-primary",namespace="database",validation_type="checksum",result="failure"} 2
```

### 10. 系统信息

**指标名称**: `backup_manager_info`

**类型**: Info

**标签**:
- `version`: 备份管理器版本
- `python_version`: Python 版本
- `k8s_version`: Kubernetes 版本

**说明**: 记录系统信息

**示例**:
```
backup_manager_info_info{version="0.2.0",python_version="3.9.0",k8s_version="1.28.0"} 1.0
```

## 使用方法

### 1. 在代码中使用

```python
from utils.metrics import get_metrics

# 获取全局指标实例
metrics = get_metrics()

# 记录备份成功
metrics.record_backup_success(
    app_name='mysql-primary',
    namespace='database',
    app_type='mysql',
    duration=45.5,
    size=104857600  # 100MB
)

# 记录备份失败
metrics.record_backup_failure(
    app_name='mysql-primary',
    namespace='database',
    app_type='mysql',
    error_type='connection_error'
)

# 记录应用发现
metrics.record_apps_discovered(
    namespace='database',
    resource_type='StatefulSet',
    count=5
)
```

### 2. 暴露指标端点

在主程序中添加 HTTP 服务器暴露指标:

```python
from prometheus_client import start_http_server
from utils.metrics import init_metrics

# 初始化指标
metrics = init_metrics()

# 启动 HTTP 服务器 (端口 8000)
start_http_server(8000)

# 设置系统信息
metrics.set_system_info(
    version='0.2.0',
    python_version='3.9.0',
    k8s_version='1.28.0'
)
```

### 3. Prometheus 配置

在 Prometheus 配置文件中添加抓取目标:

```yaml
scrape_configs:
  - job_name: 'k8s-backup-manager'
    static_configs:
      - targets: ['backup-manager:8000']
    scrape_interval: 30s
```

### 4. Kubernetes 部署

在 Deployment 中添加指标端口:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backup-manager-metrics
  labels:
    app: backup-manager
spec:
  ports:
  - name: metrics
    port: 8000
    targetPort: 8000
  selector:
    app: backup-manager
---
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: backup-manager
spec:
  selector:
    matchLabels:
      app: backup-manager
  endpoints:
  - port: metrics
    interval: 30s
```

## Grafana 仪表板

### 推荐面板

#### 1. 备份成功率

```promql
rate(backup_operations_total{status="success"}[5m]) / 
rate(backup_operations_total[5m]) * 100
```

#### 2. 平均备份耗时

```promql
rate(backup_duration_seconds_sum[5m]) / 
rate(backup_duration_seconds_count[5m])
```

#### 3. 备份失败率

```promql
rate(backup_operations_total{status="failure"}[5m])
```

#### 4. 存储使用量

```promql
backup_storage_used_bytes
```

#### 5. 正在进行的备份

```promql
sum(backups_in_progress)
```

#### 6. 重试次数

```promql
rate(backup_retry_operations_total[5m])
```

## 告警规则

### 1. 备份失败告警

```yaml
- alert: BackupFailureRate
  expr: rate(backup_operations_total{status="failure"}[5m]) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "备份失败率过高"
    description: "{{ $labels.namespace }}/{{ $labels.app_name }} 备份失败率超过 10%"
```

### 2. 备份耗时过长告警

```yaml
- alert: BackupDurationHigh
  expr: backup_duration_seconds > 3600
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "备份耗时过长"
    description: "{{ $labels.namespace }}/{{ $labels.app_name }} 备份耗时超过 1 小时"
```

### 3. 存储空间不足告警

```yaml
- alert: BackupStorageLow
  expr: backup_storage_used_bytes > 900000000000  # 900GB
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "备份存储空间不足"
    description: "{{ $labels.storage_type }}/{{ $labels.location }} 存储使用量超过 900GB"
```

### 4. 备份长时间未成功告警

```yaml
- alert: BackupNotSuccessful
  expr: time() - last_backup_success_timestamp > 86400  # 24小时
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "备份长时间未成功"
    description: "{{ $labels.namespace }}/{{ $labels.app_name }} 超过 24 小时未成功备份"
```

## 测试

运行监控指标测试:

```bash
# 运行所有监控测试
python -m pytest tests/test_metrics.py -v

# 运行特定测试
python -m pytest tests/test_metrics.py::TestBackupMetrics::test_record_backup_success -v
```

## 相关资源

- [Prometheus 文档](https://prometheus.io/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [Grafana 文档](https://grafana.com/docs/)

## 更新日志

- **2026-04-01**: 添加 Prometheus 监控指标支持
  - 实现 `metrics.py` 监控模块
  - 添加 10 种监控指标
  - 添加单元测试
  - 添加文档和示例
