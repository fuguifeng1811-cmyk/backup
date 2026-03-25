# 备份验证功能

K8s Backup Manager 提供了全面的备份验证功能，确保备份文件的完整性和可用性。

## 验证功能介绍

备份验证功能提供以下验证类型：

1. **校验和验证**：计算备份文件的哈希值并验证完整性
2. **内容验证**：检查备份文件的内容格式是否正确
3. **元数据验证**：验证备份文件的元数据（大小、修改时间等）

## 启用备份验证

### 1. 通过配置文件启用

在配置文件中启用备份验证：

```yaml
# config.yaml
backup:
  # ... 其他配置
  validation:
    enabled: true
    methods:
      - checksum      # 校验和验证
      - content       # 内容验证
    checksum_algorithm: "sha256"  # 校验算法
    verification_on_backup: true  # 备份完成后自动验证
```

### 2. 通过应用注解启用

通过Kubernetes应用注解启用备份验证：

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql-primary
  annotations:
    # 备份配置
    backup.k8s.io/enabled: "true"
    backup.k8s.io/app-type: "mysql"
    backup.k8s.io/schedule: "0 2 * * *"

    # 验证配置
    backup.k8s.io/validation-enabled: "true"
    backup.k8s.io/validation-methods: "checksum,content"  # 验证方法逗号分隔
    backup.k8s.io/checksum-algorithm: "sha256"
spec:
  # ... StatefulSet配置
```

## 验证脚本使用

### 1. 手动运行验证

可以手动运行备份验证脚本：

```bash
# 设置环境变量
export APP_TYPE=mysql
export BACKUP_DIR=/backup/mysql
export VERIFY_METHOD=both  # checksum, content, both
export ALGORITHM=sha256

# 运行验证
./scripts/backup-verify.sh
```

### 2. 在备份作业中启用验证

在生成的备份作业中会自动包含验证步骤：

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mysql-backup-validation
spec:
  template:
    spec:
      containers:
      - name: validate
        image: your-registry/k8s-backup-manager:latest
        command: ["/bin/sh", "-c"]
        args:
        - |
          # 下载验证脚本
          curl -sSL -o /tmp/backup-verify.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/backup-verify.sh
          chmod +x /tmp/backup-verify.sh

          # 运行验证
          APP_TYPE=mysql VERIFY_METHOD=both /tmp/backup-verify.sh
        env:
        - name: BACKUP_DIR
          value: "/backup"
        - name: APP_TYPE
          value: "mysql"
        - name: VERIFY_METHOD
          value: "both"
        volumeMounts:
        - name: backup-storage
          mountPath: /backup
      volumes:
      - name: backup-storage
        persistentVolumeClaim:
          claimName: mysql-backup-pvc
      restartPolicy: Never
```

## 验证报告

备份验证完成后会生成JSON格式的验证报告：

```json
{
  "verification": {
    "timestamp": "2026-03-25T10:30:00Z",
    "app_type": "mysql",
    "verify_method": "both",
    "algorithm": "sha256",
    "backup_directory": "/backup",
    "results": {
      "checksum_validation": true,
      "content_validation": true,
      "passed": true,
      "details": "Validation completed successfully"
    }
  }
}
```

## Python API 使用

可以在Python代码中使用验证器：

```python
from src.validator.backup_validator import BackupValidator

# 创建验证器
validator = BackupValidator()

# 计算文件校验和
checksum = validator.calculate_checksum('/backup/mysql_backup.sql.gz')

# 验证备份完整性
is_valid, errors = validator.verify_backup_integrity('/backup/backup_verification.json')

# 验证备份内容
content_valid, msg = validator.verify_backup_content('/backup/mysql_backup.sql.gz', 'mysql')
```

## 故障排除

### 验证失败

如果验证失败，检查以下内容：

1. 备份文件是否完整
2. 网络连接是否稳定
3. 存储空间是否充足
4. 权限设置是否正确

### 性能考虑

对于大型备份文件，验证过程可能需要较长时间。可以：

1. 使用更快的校验算法（如MD5，但安全性较低）
2. 对于超大文件，只验证文件头部和尾部
3. 并行验证多个小文件