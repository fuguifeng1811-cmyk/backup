# PVC 数据备份配置示例

## 适用场景

- NFS 挂载的数据
- CephFS 挂载的数据
- 本地文件存储（如 WordPress 上传目录）
- 无数据库的有状态应用数据

## 应用信息示例

- **类型**: Deployment
- **名称**: wordpress
- **命名空间**: web
- **PVC**: wordpress-data (50Gi, RWO)

## 备份策略选择

### 方式 1: 使用 rsync（增量备份）

适合频繁备份、数据量大的场景。

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wordpress-backup-rsync
  namespace: web
spec:
  schedule: "0 */6 * * *"  # 每 6 小时
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: pvc-backup
            image: alpine:latest
            command: ["/bin/sh", "-c"]
            args:
            - |
              apk add --no-cache rsync && \
              /scripts/pvc-backup.sh
            env:
            - name: SOURCE_DIR
              value: "/data"
            - name: BACKUP_DIR
              value: "/backup"
            - name: BACKUP_METHOD
              value: "rsync"
            - name: APP_NAME
              value: "wordpress"
            - name: EXCLUDE_PATTERNS
              value: "wp-content/cache wp-content/uploads/*/.thumbs"
            - name: RETENTION_DAYS
              value: "14"
            volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: data
              mountPath: /data
              readOnly: true  # 只读挂载避免影响应用
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: data
            persistentVolumeClaim:
              claimName: wordpress-data
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
```

### 方式 2: 使用 tar（全量备份）

适合定期完整备份、数据量较小的场景。

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wordpress-backup-tar
  namespace: web
spec:
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: pvc-backup
            image: alpine:latest
            command: ["/bin/sh", "-c"]
            args:
            - |
              apk add --no-cache tar gzip && \
              /scripts/pvc-backup.sh
            env:
            - name: SOURCE_DIR
              value: "/data"
            - name: BACKUP_DIR
              value: "/backup"
            - name: BACKUP_METHOD
              value: "tar"
            - name: APP_NAME
              value: "wordpress"
            - name: EXCLUDE_PATTERNS
              value: "*.tmp *.log wp-content/cache/*"
            - name: RETENTION_DAYS
              value: "7"
            volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: data
              mountPath: /data
              readOnly: true
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: data
            persistentVolumeClaim:
              claimName: wordpress-data
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
```

### 方式 3: 使用 VolumeSnapshot（快照备份）

适合支持 CSI 快照的存储（如 Ceph RBD、AWS EBS、GCP PD）。

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: csi-ceph-snapshotclass
  annotations:
    snapshot.storage.kubernetes.io/is-default-class: "true"
driver: ceph.csi.io/rbd
deletionPolicy: Delete
parameters:
  clusterID: rook-ceph
  csi.storage.k8s.io/snapshotter-secret-name: csi-rbd-secret
  csi.storage.k8s.io/snapshotter-secret-namespace: rook-ceph
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wordpress-backup-snapshot
  namespace: web
spec:
  schedule: "0 1 * * 0"  # 每周日凌晨 1 点
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          serviceAccountName: backup-sa
          containers:
          - name: snapshot-backup
            image: bitnami/kubectl:latest
            command: ["/bin/sh", "-c"]
            args:
            - |
              # 生成快照名称
              SNAPSHOT_NAME="wordpress-data-snapshot-$(date +%Y%m%d-%H%M%S)"

              # 创建 VolumeSnapshot
              cat <<EOF | kubectl apply -f -
              apiVersion: snapshot.storage.k8s.io/v1
              kind: VolumeSnapshot
              metadata:
                name: $SNAPSHOT_NAME
                namespace: web
              spec:
                volumeSnapshotClassName: csi-ceph-snapshotclass
                source:
                  persistentVolumeClaimName: wordpress-data
              EOF

              echo "VolumeSnapshot 创建成功: $SNAPSHOT_NAME"

              # 等待快照完成
              kubectl wait --for=condition=ready volumesnapshot/$SNAPSHOT_NAME --timeout=300s -n web

              echo "快照完成: $SNAPSHOT_NAME"
            volumeMounts:
            - name: kubeconfig
              mountPath: /root/.kube
          volumes:
          - name: kubeconfig
            secret:
              secretName: backup-kubeconfig
```

## 多应用统一备份

如果需要备份多个应用的 PVC:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: multi-app-backup
  namespace: backup
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: multi-backup
            image: alpine:latest
            command: ["/bin/sh", "-c"]
            args:
            - |
              apk add --no-cache rsync tar gzip

              # 备份应用 1
              export SOURCE_DIR="/app1-data"
              export BACKUP_DIR="/backup/app1"
              export APP_NAME="app1"
              /scripts/pvc-backup.sh

              # 备份应用 2
              export SOURCE_DIR="/app2-data"
              export BACKUP_DIR="/backup/app2"
              export APP_NAME="app2"
              /scripts/pvc-backup.sh
            env:
            - name: RETENTION_DAYS
              value: "7"
            volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: app1-data
              mountPath: /app1-data
              readOnly: true
            - name: app2-data
              mountPath: /app2-data
              readOnly: true
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: scripts
            configMap:
              name: backup-scripts
          - name: app1-data
            persistentVolumeClaim:
              claimName: app1-data-pvc
          - name: app2-data
            persistentVolumeClaim:
              claimName: app2-data-pvc
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
```

## 恢复步骤

### 使用 rsync 恢复

```bash
# 恢复到指定时间点的备份
BACKUP_DATE="20260324"
rsync -av --delete /backup/wordpress_${BACKUP_DATE}/ /data/
```

### 使用 tar 恢复

```bash
# 解压备份
tar -xzf /backup/wordpress_20260325_020000.tar.gz -C /data/

# 或恢复到临时目录再手动验证
tar -xzf /backup/wordpress_20260325_020000.tar.gz -C /tmp/restore/
```

### 使用 VolumeSnapshot 恢复

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: wordpress-data-restored
  namespace: web
spec:
  dataSource:
    name: wordpress-data-snapshot-20260324-010000
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: ceph-block
```

## 备份验证脚本

```bash
#!/bin/bash
# 验证 PVC 备份完整性

APP_NAME="wordpress"
BACKUP_DIR="/backup/${APP_NAME}"
EXPECTED_FILE="wp-config.php"

# 查找最新的备份
LATEST_BACKUP=$(find "${BACKUP_DIR}" -name "${APP_NAME}_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)

if [ -z "${LATEST_BACKUP}" ]; then
    echo "✗ 未找到备份文件"
    exit 1
fi

# 验证备份文件完整性
if tar -tzf "${LATEST_BACKUP}" "${EXPECTED_FILE}" > /dev/null 2>&1; then
    echo "✓ 备份文件验证成功: ${LATEST_BACKUP}"
    echo "  包含关键文件: ${EXPECTED_FILE}"
else
    echo "✗ 备份文件损坏或缺失关键文件: ${LATEST_BACKUP}"
    exit 1
fi
```

## 注意事项

1. **只读挂载**: 备份时建议以只读方式挂载源 PVC，避免影响正在运行的应用

2. **排除缓存**: 使用 `EXCLUDE_PATTERNS` 排除临时文件和缓存，减小备份大小

3. **备份窗口**: 选择业务低峰期进行备份，减少对应用的影响

4. **存储性能**: 确保备份存储有足够的 IOPS 和带宽

5. **快照支持**: 使用 VolumeSnapshot 前，确认存储系统和 CSI 驱动支持快照功能

6. **应用一致性**:
   - 对于数据库，建议先停止写入或使用应用一致性快照
   - 对于文件服务，建议使用应用级别的冻结/解冻机制

7. **离线环境**: 在离线环境中，需提前将所需镜像导入私有仓库
