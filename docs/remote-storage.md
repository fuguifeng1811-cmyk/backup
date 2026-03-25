# 远程存储支持

本文档介绍了K8s Backup Manager对远程存储的支持，包括S3兼容存储（AWS S3、MinIO、Ceph RGW等）。

## 支持的远程存储类型

- AWS S3
- MinIO
- Ceph RGW (RADOS Gateway)
- 其他兼容S3协议的对象存储

## 配置远程存储

### 1. 通过配置文件启用远程存储

在备份配置中添加远程存储设置：

```yaml
# config.yaml
backup:
  # ... 其他配置
  remote_storage:
    enabled: true
    type: "s3"
    s3:
      endpoint: "https://s3.example.com"  # S3服务端点
      bucket: "backup-bucket"             # 存储桶名称
      region: "us-east-1"                 # 区域
```

### 2. 在应用注解中配置远程存储

可以通过Kubernetes应用的注解来配置远程存储：

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql-primary
  annotations:
    # 启用备份
    backup.k8s.io/enabled: "true"
    backup.k8s.io/app-type: "mysql"
    backup.k8s.io/schedule: "0 2 * * *"

    # 远程存储配置
    backup.k8s.io/remote-storage-enabled: "true"
    backup.k8s.io/remote-storage-type: "s3"
    backup.k8s.io/s3-endpoint: "https://s3.example.com"
    backup.k8s.io/s3-bucket: "mysql-backups"
    backup.k8s.io/s3-region: "us-east-1"
spec:
  # ... StatefulSet配置
```

### 3. 创建S3凭证Secret

需要创建包含S3访问凭证的Secret：

```bash
kubectl create secret generic mysql-backup-secret \
  --from-literal=S3_ACCESS_KEY='your-access-key' \
  --from-literal=S3_SECRET_KEY='your-secret-key' \
  --from-literal=MYSQL_PASSWORD='your-mysql-password' \
  -n database
```

## 工作流程

1. **本地备份**: 首先在本地PVC上创建备份文件
2. **上传到远程存储**: 使用AWS CLI将备份文件上传到S3兼容存储
3. **清理本地文件**: 根据保留策略清理本地备份文件

## 安全特性

- 通过Secret管理S3访问凭证
- 使用临时配置文件避免命令行泄露密码
- AWS CLI配置文件权限设置为600（仅所有者可读写）
- 支持IAM角色（如果在EC2实例上运行）

## Helm Chart配置

在Helm Chart中也可以配置远程存储：

```yaml
# values.yaml
remoteStorage:
  enabled: true
  type: "s3"
  s3:
    endpoint: "https://s3.example.com"
    bucket: "backup-bucket"
    region: "us-east-1"
    credentials:
      existingSecret: "s3-credentials-secret"  # 使用现有的Secret
      # 或者直接指定（不推荐）
      # accessKey: "your-access-key"
      # secretKey: "your-secret-key"
```

## 故障排除

### 上传失败
- 检查S3端点URL是否正确
- 验证访问凭证是否有效
- 确认目标存储桶是否存在

### 网络连接问题
- 检查网络策略是否允许到S3端点的连接
- 验证DNS解析是否正确

### 权限问题
- 确认S3 IAM策略允许上传操作
- 检查S3存储桶策略