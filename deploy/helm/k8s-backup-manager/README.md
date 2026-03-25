# Helm Chart 部署示例

## 快速开始

### 1. 添加 Chart 仓库（可选）

```bash
# 本地 Chart 目录
helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace
```

### 2. 使用自定义 values.yaml

```bash
helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace \
  -f custom-values.yaml
```

### 3. 配置示例

#### 仅发现模式 (discover)

```yaml
# values-discover.yaml
backupManager:
  mode: discover
  namespaces:
    - database
    - app-production

image:
  repository: your-registry/k8s-backup-manager
  tag: "0.1.0"
```

#### 生成模式 (generate)

```yaml
# values-generate.yaml
backupManager:
  mode: generate
  namespaces:
    - database
  outputDir: /app/manifests

backupStorage:
  enabled: true
  storageClassName: "ceph-block"
  size: 500Gi

# 配置邮件通知
backupManager:
  config:
    email:
      enabled: true
      smtp_host: "smtp.example.com"
      smtp_port: 587
      smtp_username: "backup@example.com"
      from_address: "backup@example.com"
      to_addresses:
        - "admin@example.com"
        - "ops@example.com"
```

#### 定时任务模式 (cron)

```yaml
# values-cron.yaml
backupManager:
  mode: cron

cronjob:
  enabled: true
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  concurrencyPolicy: Forbid

# 其他配置...
```

### 4. 部署命令

```bash
# 仅发现应用（一次性 Job）
helm install backup-discover ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace \
  -f values-discover.yaml

# 生成备份清单（一次性 Job）
helm install backup-generate ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace \
  -f values-generate.yaml

# 定时运行（CronJob）
helm install backup-cron ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace \
  -f values-cron.yaml
```

### 5. 查看部署状态

```bash
# 查看 Job/CronJob
kubectl get jobs -n backup
kubectl get cronjobs -n backup

# 查看 Pod 日志
kubectl logs -l app.kubernetes.io/instance=backup-discover -n backup

# 查看生成的清单
kubectl get configmap -n backup
```

### 6. 卸载

```bash
helm uninstall backup-discover -n backup
```

## 高级配置

### 使用私有镜像仓库

```yaml
image:
  repository: registry.example.com/k8s-backup-manager
  tag: "0.1.0"
  pullSecrets:
    - name: registry-secret

# 创建 Secret
kubectl create secret docker-registry registry-secret \
  --docker-server=registry.example.com \
  --docker-username=your-user \
  --docker-password=your-password \
  --docker-email=your-email@example.com \
  -n backup
```

### 自定义备份脚本

```yaml
backupScripts:
  enabled: true
  scripts:
    mysql: |
      #!/bin/bash
      # 自定义 MySQL 备份脚本
      echo "Running custom MySQL backup..."
      # ... your script here
    postgresql: |
      #!/bin/bash
      # 自定义 PostgreSQL 备份脚本
      echo "Running custom PostgreSQL backup..."
```

### 指定节点运行

```yaml
nodeSelector:
  kubernetes.io/hostname: backup-node-1

tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "backup"
    effect: "NoSchedule"
```

### 资源限制

```yaml
resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 256Mi
```

## 离线环境部署

### 1. 导出 Chart

```bash
helm package ./deploy/helm/k8s-backup-manager
# 生成: k8s-backup-manager-0.1.0.tgz
```

### 2. 导入镜像

```bash
# 保存镜像
docker save your-registry/k8s-backup-manager:0.1.0 -o k8s-backup-manager.tar

# 在离线环境加载
docker load -i k8s-backup-manager.tar
```

### 3. 部署

```bash
helm install k8s-backup-manager k8s-backup-manager-0.1.0.tgz \
  --namespace backup \
  --create-namespace
```

## 故障排查

### 查看 Job 状态

```bash
kubectl describe job <job-name> -n backup
```

### 查看 Pod 日志

```bash
kubectl logs -l job-name=<job-name> -n backup --tail=100
```

### 查看事件

```bash
kubectl get events -n backup --sort-by='.lastTimestamp'
```

### 手动运行测试

```bash
# 进入 Pod 手动测试
kubectl run backup-test \
  --image=your-registry/k8s-backup-manager:0.1.0 \
  --namespace backup \
  -it --rm --restart=Never -- /bin/bash

# 在容器内运行
python src/main.py discover
```
