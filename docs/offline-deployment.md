# 离线环境部署

本文档说明如何在没有互联网连接的环境中部署和使用K8s Backup Manager。

## 问题背景

在离线环境中，备份作业通常需要从外部源（如GitHub）下载备份脚本。由于没有网络连接，这些下载请求会失败，导致备份作业无法正常运行。

## 解决方案

通过使用Kubernetes ConfigMap将备份脚本预加载到集群中，然后在备份作业中挂载这些脚本，从而避免在运行时下载。

## 部署步骤

### 1. 准备备份脚本

在有网络连接的环境中，获取所有备份脚本：

```bash
# 克隆备份管理器仓库
git clone https://github.com/your-repo/backup.git
cd backup

# 复制脚本到单独目录
mkdir -p offline-scripts
cp scripts/*.sh offline-scripts/
```

### 2. 创建脚本 ConfigMap

在离线环境中，创建包含所有备份脚本的ConfigMap：

```bash
# 使用kubectl创建ConfigMap
kubectl create configmap mysql-backup-scripts \
  --from-file=scripts/ \
  --dry-run=client \
  -o yaml > mysql-backup-scripts.yaml

# 应用到集群
kubectl apply -f mysql-backup-scripts.yaml
```

### 3. 配置备份应用使用离线模式

在备份配置中启用离线模式：

```yaml
# config.yaml
backup:
  # ... 其他配置
  offline_mode: true  # 启用离线模式
  storage:
    # ... 存储配置
```

或者通过应用注解：

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

    # 离线模式配置
    backup.k8s.io/offline-mode: "true"
spec:
  # ... StatefulSet配置
```

### 4. 使用Helm Chart部署（推荐）

使用Helm Chart可以更方便地配置离线模式：

```bash
# 在values.yaml中启用离线模式
cat <<EOF > values-offline.yaml
backupManager:
  config:
    backup:
      offline_mode: true

# 使用离线模式部署
helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  -f values-offline.yaml
```

## 工作原理

1. **脚本预加载**：备份脚本被打包到ConfigMap中，预先存储在Kubernetes集群中
2. **挂载脚本**：备份作业启动时，将脚本从ConfigMap挂载到容器的 `/scripts` 目录
3. **离线执行**：备份作业使用本地挂载的脚本，无需从外部下载

## ConfigMap结构

创建的ConfigMap包含以下脚本：

- `mysql-backup.sh` - MySQL备份脚本
- `postgresql-backup.sh` - PostgreSQL备份脚本
- `redis-backup.sh` - Redis备份脚本
- `minio-backup.sh` - MinIO备份脚本
- `pvc-backup.sh` - 通用PVC备份脚本
- `remote-upload.sh` - 远程上传脚本
- `backup-verify.sh` - 备份验证脚本

## Pod配置示例

在启用离线模式时，生成的备份作业Pod将包含以下配置：

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: backup
    image: your-registry/backup-agent:latest
    command: ["/bin/sh", "-c"]
    args:
    - |
      # 使用挂载的脚本
      chmod +x /scripts/mysql-backup.sh
      /scripts/mysql-backup.sh
    volumeMounts:
    - name: backup-scripts
      mountPath: /scripts
      readOnly: true
    - name: backup-storage
      mountPath: /backup
  volumes:
  - name: backup-scripts
    configMap:
      name: mysql-backup-scripts
      defaultMode: 0755  # 确保脚本可执行
  - name: backup-storage
    persistentVolumeClaim:
      claimName: mysql-backup-pvc
```

## 验证部署

1. **检查ConfigMap**：
   ```bash
   kubectl get configmap mysql-backup-scripts -o yaml
   ```

2. **检查备份作业**：
   ```bash
   kubectl get jobs -l backup-job
   kubectl logs job-name
   ```

3. **确认脚本挂载**：
   ```bash
   kubectl exec -it pod-name -- ls -la /scripts
   ```

## 注意事项

- **脚本更新**：当备份脚本更新时，需要重新创建ConfigMap
- **权限设置**：ConfigMap中的脚本需要设置适当的执行权限
- **容量规划**：ConfigMap有大小限制（1MB），适用于存储小型脚本
- **安全考虑**：确保只有授权用户可以修改备份脚本ConfigMap

## 故障排除

### 脚本权限错误
如果遇到权限错误，确保ConfigMap的defaultMode设置为0755或类似值，以便脚本可执行。

### ConfigMap不存在
确认ConfigMap已正确创建并存在于备份作业的目标命名空间中。

### 挂载失败
检查Pod的卷挂载配置，确保卷名和挂载路径正确。