# S3 远程存储备份示例

此示例演示如何配置MySQL备份并将备份文件上传到S3兼容存储。

## 1. 创建S3凭证Secret

```bash
kubectl create secret generic mysql-s3-backup-secret \
  --from-literal=S3_ACCESS_KEY='your-access-key' \
  --from-literal=S3_SECRET_KEY='your-secret-key' \
  --from-literal=MYSQL_PASSWORD='your-mysql-password' \
  -n database
```

## 2. 配置MySQL应用注解

在你的MySQL StatefulSet中添加以下注解：

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql-primary
  namespace: database
  annotations:
    # 备份配置
    backup.k8s.io/enabled: "true"
    backup.k8s.io/app-type: "mysql"
    backup.k8s.io/schedule: "0 2 * * *"  # 每天凌晨2点执行

    # 远程存储配置
    backup.k8s.io/remote-storage-enabled: "true"
    backup.k8s.io/remote-storage-type: "s3"
    backup.k8s.io/s3-endpoint: "https://s3.example.com"
    backup.k8s.io/s3-bucket: "mysql-backups"
    backup.k8s.io/s3-region: "us-east-1"

    # 备份参数
    backup.k8s.io/mysql-user: "backup"
    backup.k8s.io/mysql-database: "app_db"
spec:
  # ... StatefulSet配置
```

## 3. 运行备份管理器发现

```bash
# 发现带有备份配置的应用
python src/main.py discover --namespace database

# 生成备份配置清单
python src/main.py generate --namespace database --output manifests/
```

## 4. 生成的备份资源配置

备份管理器将生成包含以下内容的资源：

### CronJob (定期备份)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mysql-primary-backup
  namespace: database
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: your-registry/k8s-backup-manager:latest
            command: ["/bin/sh", "-c"]
            args:
            - |
              # 执行MySQL备份
              curl -sSL -o /tmp/mysql-backup.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/mysql-backup.sh
              chmod +x /tmp/mysql-backup.sh
              MYSQL_HOST=mysql-primary-0.mysql-primary.database.svc.cluster.local MYSQL_USER=backup MYSQL_DATABASE=app_db /tmp/mysql-backup.sh

              # 上传到S3
              curl -sSL -o /tmp/remote-upload.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/remote-upload.sh
              chmod +x /tmp/remote-upload.sh
              REMOTE_STORAGE_TYPE=s3 S3_ENDPOINT=https://s3.example.com S3_BUCKET=mysql-backups /tmp/remote-upload.sh
            env:
            - name: REMOTE_STORAGE_ENABLED
              value: "true"
            - name: REMOTE_STORAGE_TYPE
              value: "s3"
            - name: S3_ENDPOINT
              value: "https://s3.example.com"
            - name: S3_BUCKET
              value: "mysql-backups"
            - name: S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: mysql-s3-backup-secret
                  key: S3_ACCESS_KEY
            - name: S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: mysql-s3-backup-secret
                  key: S3_SECRET_KEY
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: mysql-primary-backup-pvc
          restartPolicy: Never
```

### Secret (包含S3凭证)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql-s3-backup-secret
  namespace: database
type: Opaque
stringData:
  S3_ACCESS_KEY: 'your-access-key'
  S3_SECRET_KEY: 'your-secret-key'
  MYSQL_PASSWORD: 'your-mysql-password'
```

## 5. 部署备份配置

```bash
# 应用生成的备份配置
kubectl apply -f manifests/ -n database
```

## 6. 验证备份作业

```bash
# 查看CronJob
kubectl get cronjob -n database

# 查看备份作业
kubectl get jobs -n database

# 查看备份Pod日志
kubectl logs -l job-name=<job-name> -n database
```

## 7. 检查S3存储

备份文件将被上传到指定的S3存储桶中，你可以通过S3控制台或CLI检查备份文件。

## 注意事项

1. **安全**: 确保S3凭证通过Secret安全地传递给备份作业
2. **网络**: 确保Kubernetes集群可以访问S3端点
3. **权限**: 验证S3访问凭证具有足够的权限来上传文件到目标存储桶
4. **成本**: 考虑S3存储和传输的成本
5. **合规性**: 验证S3提供商符合你的数据合规要求