# K8s Backup Manager - 容器化部署指南

## 📋 概述

本文档介绍如何将 K8s Backup Manager 容器化部署到 Kubernetes 集群。

## 🚀 快速开始

### 方式 1: Docker 镜像 + kubectl (最简单)

```bash
# 1. 构建镜像
docker build -t your-registry/k8s-backup-manager:0.1.0 .

# 2. 推送到镜像仓库
docker push your-registry/k8s-backup-manager:0.1.0

# 3. 使用 Kustomize 部署
kubectl apply -k deploy/kustomize/base

# 4. 查看部署状态
kubectl get jobs -n backup
kubectl logs -l app=k8s-backup-manager -n backup
```

### 方式 2: Helm Chart (推荐)

```bash
# 1. 构建镜像并推送
make build
make push

# 2. 使用 Helm 部署
helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace

# 3. 查看状态
helm status k8s-backup-manager -n backup
kubectl get pods -n backup
```

### 方式 3: Makefile (最便捷)

```bash
# 一键部署（使用 Helm）
make deploy-helm

# 或使用 Kustomize
make deploy-kustomize
```

## 📦 Docker 镜像

### 构建镜像

```bash
# 标准镜像（基于 Debian）
docker build -t your-registry/k8s-backup-manager:0.1.0 .

# Alpine 镜像（更小）
docker build -f Dockerfile.alpine -t your-registry/k8s-backup-manager:0.1.0-alpine .

# 指定版本和仓库
docker build -t registry.example.com/backup/k8s-backup-manager:0.1.0 .
```

### 镜像大小优化

使用多阶段构建，镜像大小约 **150-200MB**。

```bash
# 查看镜像大小
docker images | grep k8s-backup-manager
```

### 推送到私有仓库

```bash
# 登录私有仓库
docker login registry.example.com

# 推送镜像
docker push registry.example.com/k8s-backup-manager:0.1.0
```

### 离线环境部署

```bash
# 1. 保存镜像
docker save your-registry/k8s-backup-manager:0.1.0 -o k8s-backup-manager.tar

# 2. 复制到离线环境
scp k8s-backup-manager.tar user@offline-host:/tmp/

# 3. 在离线环境加载
docker load -i /tmp/k8s-backup-manager.tar

# 4. 修改镜像地址（如果需要）
docker tag your-registry/k8s-backup-manager:0.1.0 offline-registry/k8s-backup-manager:0.1.0
```

## 🎯 Helm Chart 部署

### 1. 准备 values.yaml

创建自定义配置 `custom-values.yaml`:

```yaml
# 镜像配置
image:
  repository: your-registry/k8s-backup-manager
  tag: "0.1.0"
  pullPolicy: IfNotPresent

# 备份管理器配置
backupManager:
  mode: discover  # discover, generate, or cron
  namespaces:
    - database
    - app-production

# 定时任务配置
cronjob:
  enabled: true
  schedule: "0 2 * * *"  # 每天凌晨 2 点

# 备份存储
backupStorage:
  enabled: true
  storageClassName: "ceph-block"
  size: 500Gi

# 资源限制
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi
```

### 2. 部署命令

```bash
# 安装（首次部署）
helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  --create-namespace \
  -f custom-values.yaml

# 升级（配置变更）
helm upgrade k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  -f custom-values.yaml

# 查看状态
helm status k8s-backup-manager -n backup

# 查看 Release 历史
helm history k8s-backup-manager -n backup

# 回滚到上一个版本
helm rollback k8s-backup-manager -n backup
```

### 3. 不同场景配置

#### 场景 1: 仅发现模式

```yaml
backupManager:
  mode: discover
  namespaces:
    - default
    - database
```

#### 场景 2: 生成备份清单模式

```yaml
backupManager:
  mode: generate
  namespaces:
    - database
  outputDir: /app/manifests

backupStorage:
  enabled: true
  size: 100Gi
```

#### 场景 3: 定时运行模式

```yaml
backupManager:
  mode: cron

cronjob:
  enabled: true
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  concurrencyPolicy: Forbid

job:
  ttlSecondsAfterFinished: 86400  # 24 小时后自动清理
```

### 4. 高级配置

#### 使用私有镜像仓库

```bash
# 创建 Secret
kubectl create secret docker-registry registry-secret \
  --docker-server=registry.example.com \
  --docker-username=your-user \
  --docker-password=your-password \
  -n backup

# values.yaml
image:
  pullSecrets:
    - name: registry-secret
```

#### 节点选择

```yaml
nodeSelector:
  kubernetes.io/hostname: backup-node-1

tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "backup"
    effect: "NoSchedule"
```

#### 邮件通知

```yaml
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
```

## 🔧 Kustomize 部署

### 1. Base 配置

```bash
# 部署基础配置
kubectl apply -k deploy/kustomize/base

# 查看生成的资源
kustomize build deploy/kustomize/base | less
```

### 2. Production Overlay

```bash
# 部署到生产环境
kubectl apply -k deploy/kustomize/overlays/production

# 查看生产环境配置
kustomize build deploy/kustomize/overlays/production | less
```

### 3. Development Overlay

```bash
# 部署到开发环境
kubectl apply -k deploy/kustomize/overlays/development
```

### 4. 自定义 Overlay

创建自定义 overlay:

```bash
mkdir -p deploy/kustomize/overlays/custom
cd deploy/kustomize/overlays/custom
```

`kustomization.yaml`:

```yaml
resources:
  - ../../base

patchesStrategicMerge:
  - custom-patch.yaml

namespace: backup-custom

images:
  - name: your-registry/k8s-backup-manager
    newTag: 0.1.0-custom
```

`custom-patch.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: k8s-backup-manager-backup
spec:
  resources:
    requests:
      storage: 200Gi
```

## 🐳 Docker Compose (本地测试)

### 1. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backup-manager

# 停止服务
docker-compose down
```

### 2. 进入容器调试

```bash
docker-compose exec backup-manager /bin/bash

# 在容器内运行
python src/main.py discover
```

### 3. 自定义配置

编辑 `docker-compose.yml`:

```yaml
services:
  backup-manager:
    environment:
      - LOG_LEVEL=DEBUG
    volumes:
      - ~/.kube/config:/home/backup/.kube/config:ro
      - ./config.yaml:/app/config.yaml:ro
    command: ["python", "src/main.py", "discover"]
```

## 📊 部署验证

### 1. 检查资源

```bash
# 检查 Pod
kubectl get pods -n backup
kubectl describe pod -l app=k8s-backup-manager -n backup

# 检查 Job/CronJob
kubectl get jobs -n backup
kubectl get cronjobs -n backup

# 检查 PVC
kubectl get pvc -n backup

# 检查 ConfigMap
kubectl get configmap -n backup
```

### 2. 查看日志

```bash
# 查看最近的日志
kubectl logs -l app=k8s-backup-manager -n backup --tail=100

# 实时查看日志
kubectl logs -l app=k8s-backup-manager -n backup -f

# 查看上一个容器的日志（如果重启过）
kubectl logs -l app=k8s-backup-manager -n backup --previous
```

### 3. 测试功能

```bash
# 进入容器手动测试
kubectl run backup-test \
  --image=your-registry/k8s-backup-manager:0.1.0 \
  --namespace backup \
  -it --rm --restart=Never -- /bin/bash

# 在容器内运行命令
python src/main.py discover
python src/main.py discover --namespace database
python src/main.py generate --output /tmp/test
```

## 🔒 安全配置

### 1. 使用非 root 用户

Dockerfile 已配置非 root 用户 (UID 1000):

```dockerfile
RUN useradd -m -u 1000 backup
USER backup
```

### 2. RBAC 最小权限

```yaml
rules:
  - apiGroups: [""]
    resources: ["pods", "namespaces"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["persistentvolumeclaims"]
    verbs: ["get", "list"]
  # 不授予 delete 权限，除非必要
```

### 3. 网络策略

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backup-manager-network-policy
  namespace: backup
spec:
  podSelector:
    matchLabels:
      app: k8s-backup-manager
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: database
        - podSelector:
            matchLabels:
              app: mysql
      ports:
        - protocol: TCP
          port: 3306
```

## 🔄 升级流程

### 1. 备份当前配置

```bash
# 导出当前 Helm Release 配置
helm get values k8s-backup-manager -n backup > backup-values.yaml

# 导出当前资源
kubectl get all -n backup -o yaml > backup-resources.yaml
```

### 2. 升级镜像版本

```bash
# 更新 values.yaml
image:
  tag: "0.2.0"  # 新版本

# 升级 Helm Release
helm upgrade k8s-backup-manager ./deploy/helm/k8s-backup-manager \
  --namespace backup \
  -f custom-values.yaml
```

### 3. 回滚（如果需要）

```bash
# 查看 Release 历史
helm history k8s-backup-manager -n backup

# 回滚到指定版本
helm rollback k8s-backup-manager <revision> -n backup
```

## 🐛 故障排查

### 问题 1: Pod 无法启动

```bash
# 查看 Pod 详情
kubectl describe pod -l app=k8s-backup-manager -n backup

# 常见原因:
# - 镜像拉取失败 -> 检查 imagePullSecrets
# - PVC 未绑定 -> 检查 StorageClass
# - 权限不足 -> 检查 RBAC 配置
```

### 问题 2: 连接 Kubernetes API 失败

```bash
# 检查 ServiceAccount
kubectl get sa k8s-backup-manager -n backup

# 检查 RoleBinding
kubectl get rolebinding k8s-backup-manager -n backup -o yaml

# 检查 Token
kubectl describe sa k8s-backup-manager -n backup
```

### 问题 3: 备份失败

```bash
# 查看详细日志
kubectl logs -l app=k8s-backup-manager -n backup --tail=200

# 检查配置
kubectl get configmap k8s-backup-manager-config -n backup -o yaml

# 检查存储
kubectl get pvc -n backup
```

### 问题 4: 离线环境镜像拉取失败

```bash
# 在离线环境手动加载镜像
docker load -i k8s-backup-manager.tar

# 或使用本地镜像仓库
docker tag your-registry/k8s-backup-manager:0.1.0 localhost:5000/k8s-backup-manager:0.1.0
docker push localhost:5000/k8s-backup-manager:0.1.0
```

## 📚 参考资源

- [Helm 官方文档](https://helm.sh/docs/)
- [Kustomize 官方文档](https://kustomize.io/)
- [Docker 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Kubernetes 安全最佳实践](https://kubernetes.io/docs/concepts/security/)

---

**下一步**: 配置备份策略并监控备份状态
