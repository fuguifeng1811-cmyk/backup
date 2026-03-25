# MySQL 备份配置示例

## 应用信息

- **类型**: StatefulSet
- **名称**: mysql-primary
- **命名空间**: database
- **副本数**: 3
- **PVC**: mysql-data (100Gi, RWO)

## 配置方式

### 方式 1: 使用 ConfigMap

创建 ConfigMap 包含 MySQL 连接信息:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mysql-backup-config
  namespace: database
data:
  MYSQL_HOST: "mysql-primary-0.mysql-primary.database.svc.cluster.local"
  MYSQL_PORT: "3306"
  MYSQL_USER: "backup"
  BACKUP_DIR: "/backup/mysql"
  RETENTION_DAYS: "7"
```

### 方式 2: 使用 Secret（推荐）

创建 Secret 存储敏感信息:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql-backup-secret
  namespace: database
type: Opaque
stringData:
  MYSQL_PASSWORD: "your-secure-password"
```

## 备份 Job YAML

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mysql-backup-full-$(date +%Y%m%d-%H%M%S)
  namespace: database
  labels:
    app: mysql-backup
    backup-type: full
spec:
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: backup-sa
      containers:
      - name: mysql-backup
        image: mysql:8.0
        command: ["/bin/bash", "-c"]
        args:
        - |
          # 下载备份脚本
          curl -sSL -o /scripts/mysql-backup.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/mysql-backup.sh
          chmod +x /scripts/mysql-backup.sh

          # 设置环境变量
          export BACKUP_TYPE=full
          export MYSQL_DATABASE=your_database

          # 执行备份
          /scripts/mysql-backup.sh
        env:
        - name: MYSQL_HOST
          value: "mysql-primary-0.mysql-primary.database.svc.cluster.local"
        - name: MYSQL_PORT
          value: "3306"
        - name: MYSQL_USER
          value: "backup"
        - name: MYSQL_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-backup-secret
              key: MYSQL_PASSWORD
        - name: BACKUP_DIR
          value: "/backup/mysql"
        - name: RETENTION_DAYS
          value: "7"
        volumeMounts:
        - name: backup-storage
          mountPath: /backup
      volumes:
      - name: backup-storage
        persistentVolumeClaim:
          claimName: mysql-backup-pvc
```

## CronJob 配置（定时全量备份）

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mysql-backup-daily
  namespace: database
spec:
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: mysql-backup
            image: mysql:8.0
            command: ["/bin/bash", "-c"]
            args:
            - |
              BACKUP_TYPE=full /scripts/mysql-backup.sh
            env:
            - name: MYSQL_HOST
              value: "mysql-primary-0.mysql-primary.database.svc.cluster.local"
            - name: MYSQL_PORT
              value: "3306"
            - name: MYSQL_USER
              value: "backup"
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mysql-backup-secret
                  key: MYSQL_PASSWORD
            - name: BACKUP_DIR
              value: "/backup/mysql"
            - name: RETENTION_DAYS
              value: "7"
            volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: backup-storage
            persistentVolumeClaim:
              claimName: mysql-backup-pvc
```

## Binlog 备份 CronJob（每小时）

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mysql-backup-binlog-hourly
  namespace: database
spec:
  schedule: "0 * * * *"  # 每小时
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: mysql-backup
            image: mysql:8.0
            command: ["/bin/bash", "-c"]
            args:
            - |
              BACKUP_TYPE=binlog /scripts/mysql-backup.sh
            env:
            - name: MYSQL_HOST
              value: "mysql-primary-0.mysql-primary.database.svc.cluster.local"
            - name: MYSQL_PORT
              value: "3306"
            - name: MYSQL_USER
              value: "backup"
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mysql-backup-secret
                  key: MYSQL_PASSWORD
            - name: BACKUP_DIR
              value: "/backup/mysql/binlog"
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: backup-storage
            persistentVolumeClaim:
              claimName: mysql-backup-pvc
```

## RBAC 配置

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: backup-sa
  namespace: database
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: backup-role
  namespace: database
rules:
- apiGroups: [""]
  resources: ["pods", "pods/exec"]
  verbs: ["get", "list", "create"]
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: backup-role-binding
  namespace: database
subjects:
- kind: ServiceAccount
  name: backup-sa
  namespace: database
roleRef:
  kind: Role
  name: backup-role
  apiGroup: rbac.authorization.k8s.io
```

## PVC 用于存储备份数据

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-backup-pvc
  namespace: database
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Gi
  storageClassName: your-storage-class
```

## 恢复步骤

### 恢复全量备份

```bash
# 1. 解压备份文件
gunzip mysql_full_database_20260325_020000.sql.gz

# 2. 导入数据库
mysql -h mysql-host -u root -p < mysql_full_database_20260325_020000.sql

# 3. 如果需要，应用 binlog
mysqlbinlog mysql_binlog.000001 | mysql -h mysql-host -u root -p
```

## 注意事项

1. **备份用户权限**: 确保备份用户有以下权限:
   ```sql
   GRANT SELECT, LOCK TABLES, SHOW VIEW, PROCESS, RELOAD, REPLICATION CLIENT ON *.* TO 'backup'@'%';
   ```

2. **网络策略**: 确保备份 Job 可以访问 MySQL 服务

3. **存储容量**: 监控备份存储容量，避免空间不足

4. **备份验证**: 定期验证备份文件的完整性和可恢复性

5. **离线环境**: 在离线环境中，需提前将脚本和镜像导入私有仓库
