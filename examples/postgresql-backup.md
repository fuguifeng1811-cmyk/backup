# PostgreSQL 备份配置示例

## 应用信息

- **类型**: StatefulSet
- **名称**: postgres
- **命名空间**: database
- **副本数**: 1 (主从架构需单独配置)
- **PVC**: postgres-data (200Gi, RWO)

## 配置方式

### 方式 1: 使用 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-backup-config
  namespace: database
data:
  PGHOST: "postgres-0.postgres.database.svc.cluster.local"
  PGPORT: "5432"
  PGUSER: "backup"
  PGDATABASE: "app_db"
  BACKUP_DIR: "/backup/postgresql"
  BACKUP_FORMAT: "custom"
  RETENTION_DAYS: "7"
```

### 方式 2: 使用 Secret（推荐）

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-backup-secret
  namespace: database
type: Opaque
stringData:
  PGPASSWORD: "your-secure-password"
```

## 备份 Job YAML

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: postgres-backup-full-$(date +%Y%m%d-%H%M%S)
  namespace: database
  labels:
    app: postgres-backup
    backup-type: full
spec:
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: backup-sa
      containers:
      - name: postgres-backup
        image: postgres:15
        command: ["/bin/bash", "-c"]
        args:
        - |
          # 下载备份脚本
          curl -sSL -o /scripts/postgresql-backup.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/postgresql-backup.sh
          chmod +x /scripts/postgresql-backup.sh

          # 执行备份
          /scripts/postgresql-backup.sh
        env:
        - name: PGHOST
          value: "postgres-0.postgres.database.svc.cluster.local"
        - name: PGPORT
          value: "5432"
        - name: PGUSER
          value: "backup"
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-backup-secret
              key: PGPASSWORD
        - name: PGDATABASE
          value: "app_db"
        - name: BACKUP_DIR
          value: "/backup/postgresql"
        - name: BACKUP_FORMAT
          value: "custom"
        - name: RETENTION_DAYS
          value: "7"
        volumeMounts:
        - name: backup-storage
          mountPath: /backup
      volumes:
      - name: backup-storage
        persistentVolumeClaim:
          claimName: postgres-backup-pvc
```

## CronJob 配置（定时全量备份）

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup-daily
  namespace: database
spec:
  schedule: "0 3 * * *"  # 每天凌晨 3 点
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: postgres-backup
            image: postgres:15
            command: ["/bin/bash", "-c"]
            args:
            - /scripts/postgresql-backup.sh
            env:
            - name: PGHOST
              value: "postgres-0.postgres.database.svc.cluster.local"
            - name: PGPORT
              value: "5432"
            - name: PGUSER
              value: "backup"
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-backup-secret
                  key: PGPASSWORD
            - name: PGDATABASE
              value: "app_db"
            - name: BACKUP_DIR
              value: "/backup/postgresql"
            - name: BACKUP_FORMAT
              value: "custom"
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
              claimName: postgres-backup-pvc
```

## 多数据库备份

如果需要备份多个数据库:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup-all-databases
  namespace: database
spec:
  schedule: "0 4 * * 0"  # 每周日凌晨 4 点
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: postgres-backup
            image: postgres:15
            command: ["/bin/bash", "-c"]
            args:
            - |
              # 备份所有数据库
              unset PGDATABASE
              /scripts/postgresql-backup.sh
            env:
            - name: PGHOST
              value: "postgres-0.postgres.database.svc.cluster.local"
            - name: PGPORT
              value: "5432"
            - name: PGUSER
              value: "backup"
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-backup-secret
                  key: PGPASSWORD
            - name: BACKUP_DIR
              value: "/backup/postgresql"
            - name: BACKUP_FORMAT
              value: "custom"
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: backup-storage
            persistentVolumeClaim:
              claimName: postgres-backup-pvc
```

## 恢复步骤

### 恢复单个数据库

```bash
# 1. 恢复数据库
pg_restore -h postgres-host -U postgres -d app_db /backup/postgresql/pg_app_db_20260325_030000.dump

# 或使用 SQL 格式
gunzip -c /backup/postgresql/pg_app_db_20260325_030000.sql.gz | psql -h postgres-host -U postgres -d app_db
```

### 恢复所有数据库

```bash
# 1. 恢复全局对象（角色、表空间等）
psql -h postgres-host -U postgres < /backup/postgresql/pg_all_20260325_040000.dump

# 2. 恢复各个数据库（如果需要）
pg_restore -h postgres-host -U postgres -d dbname backup_file.dump
```

## 备份验证脚本

```bash
#!/bin/bash
# 验证 PostgreSQL 备份完整性

BACKUP_FILE="/backup/postgresql/pg_app_db_$(date -d 'yesterday' +%Y%m%d)_*.dump"
if [ -f "${BACKUP_FILE}" ]; then
    # 检查备份文件是否可以正常读取
    pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ 备份文件验证成功: ${BACKUP_FILE}"
    else
        echo "✗ 备份文件损坏: ${BACKUP_FILE}"
        exit 1
    fi
else
    echo "✗ 备份文件不存在: ${BACKUP_FILE}"
    exit 1
fi
```

## 主从架构备份策略

对于 PostgreSQL 主从架构:

1. **仅备份主库**: 从库数据与主库一致，无需重复备份
2. **使用 WAL 归档**: 配合全量备份实现时间点恢复 (PITR)
3. **备份脚本优化**:
   ```bash
   # 检查是否为主库
   IS_PRIMARY=$(psql -h $PGHOST -U $PGUSER -t -c "SELECT pg_is_in_recovery()" | xargs)
   if [ "$IS_PRIMARY" = "f" ]; then
       # 执行备份
       /scripts/postgresql-backup.sh
   else
       echo "当前节点为从库，跳过备份"
   fi
   ```

## 注意事项

1. **备份用户权限**: 确保备份用户有足够的权限
   ```sql
   GRANT CONNECT ON DATABASE app_db TO backup;
   GRANT USAGE ON SCHEMA public TO backup;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO backup;
   ```

2. **备份格式选择**:
   - `custom`: 二进制格式，支持并行恢复（推荐用于生产环境）
   - `plain`: SQL 文本格式，便于查看和编辑

3. **大数据库备份**: 对于大型数据库，考虑:
   - 使用 `--jobs` 参数并行备份（pg_dump 9.3+）
   - 分库分表备份
   - 增量备份配合 WAL 归档

4. **存储容量**: 定期清理旧备份，避免存储空间不足

5. **网络策略**: 确保备份容器可以访问 PostgreSQL 服务
