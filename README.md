# K8s Backup Manager

Kubernetes 应用备份管理工具 - 自动发现有状态应用并生成备份方案

## 📋 功能特性

- ✅ 自动识别 K8s 中有状态应用（StatefulSet、使用 PVC 的 Deployment/StatefulSet/Pod）
- ✅ 从应用配置中提取备份相关信息（PVC、存储类、访问模式等）
- ✅ 支持多种备份方案（全量备份、增量备份、快照备份）
- ✅ 支持多种应用类型（MySQL、PostgreSQL、Redis、MinIO、通用 PVC）
- ✅ 备份策略配置（频率、保留策略、清理策略）
- ✅ 多种通知方式（邮件、Webhook）
- ✅ 支持多种存储后端（本地、S3、MinIO、Ceph RGW）

## 🛠 技术选型

- Python 3.6+
- Kubernetes Python Client
- PyYAML (配置文件解析)
- pathlib (文件路径处理)

## 📦 项目结构

```
k8s-backup-manager/
├── src/
│   ├── __init__.py
│   ├── main.py                # 主程序入口
│   ├── discovery/             # 应用发现模块
│   │   └── __init__.py        # 自动发现有状态应用
│   ├── extractor/             # 配置提取模块
│   ├── renderer/              # 模板渲染模块
│   └── utils/                 # 工具函数
├── scripts/                   # 备份脚本模板
│   ├── mysql-backup.sh        # MySQL 备份脚本
│   ├── postgresql-backup.sh   # PostgreSQL 备份脚本
│   ├── redis-backup.sh        # Redis 备份脚本
│   ├── minio-backup.sh        # MinIO 备份脚本
│   └── pvc-backup.sh          # 通用 PVC 备份脚本
├── examples/                  # 示例配置
│   ├── mysql-backup.md        # MySQL 备份配置示例
│   ├── postgresql-backup.md   # PostgreSQL 备份配置示例
│   └── pvc-backup.md          # PVC 备份配置示例
├── tests/                     # 测试
├── config.example.yaml        # 配置文件示例
├── config.yaml                # 主配置文件（需自行创建）
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件

复制配置文件示例并修改:

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml 配置你的环境
```

### 3. 运行应用发现

```bash
python src/main.py discover
```

或直接运行模块:

```bash
python -m src.discovery
```

### 4. 查看发现的应用

程序会输出发现的所有有状态应用及其存储信息，例如:

```json
[
  {
    "type": "StatefulSet",
    "name": "mysql-primary",
    "namespace": "database",
    "labels": {"app": "mysql"},
    "replicas": 3,
    "has_pvc": true,
    "pvc_templates": [
      {
        "name": "data",
        "storage_class": "ceph-block",
        "size": "100Gi",
        "access_modes": ["ReadWriteOnce"]
      }
    ]
  }
]
```

## 📖 使用示例

### 备份 MySQL

参考 [examples/mysql-backup.md](examples/mysql-backup.md) 获取详细的 MySQL 备份配置。

**快速开始:**

1. 创建 Secret 存储数据库密码:
   ```bash
   kubectl create secret generic mysql-backup-secret \
     --from-literal=MYSQL_PASSWORD='your-password' \
     -n database
   ```

2. 创建 CronJob 执行定期备份:
   ```bash
   kubectl apply -f examples/mysql-cronjob.yaml
   ```

### 备份 PostgreSQL

参考 [examples/postgresql-backup.md](examples/postgresql-backup.md)

### 备份通用 PVC 数据

参考 [examples/pvc-backup.md](examples/pvc-backup.md)

## 🎯 备份脚本说明

### 脚本位置

所有备份脚本位于 `scripts/` 目录:

- [mysql-backup.sh](scripts/mysql-backup.sh): MySQL 全量备份和 binlog 备份
- [postgresql-backup.sh](scripts/postgresql-backup.sh): PostgreSQL 全量备份
- [redis-backup.sh](scripts/redis-backup.sh): Redis RDB/AOF 备份
- [minio-backup.sh](scripts/minio-backup.sh): MinIO 对象存储备份
- [pvc-backup.sh](scripts/pvc-backup.sh): 通用 PVC 数据备份（支持 rsync/tar/snapshot）

### 使用备份脚本

**方式 1: 通过 Kubernetes Job**

```yaml
containers:
- name: backup
  image: mysql:8.0
  command: ["/bin/bash", "-c"]
  args:
  - |
    curl -sSL -o /tmp/mysql-backup.sh https://raw.githubusercontent.com/your-repo/backup/master/scripts/mysql-backup.sh
    chmod +x /tmp/mysql-backup.sh
    BACKUP_TYPE=full /tmp/mysql-backup.sh
```

**方式 2: 通过 ConfigMap 挂载**

```bash
# 创建 ConfigMap
kubectl create configmap backup-scripts \
  --from-file=scripts/mysql-backup.sh \
  --from-file=scripts/postgresql-backup.sh

# 在 Pod 中挂载使用
volumeMounts:
- name: scripts
  mountPath: /scripts
  readOnly: true
```

## ⚙️ 配置说明

完整的配置选项请参考 [config.example.yaml](config.example.yaml)，主要配置项:

### Kubernetes 连接

```yaml
kubernetes:
  kubeconfig: ""          # kubeconfig 路径
  context: ""             # context 名称
```

### 备份策略

```yaml
backup:
  root_path: "/data/backup"
  strategy:
    full_backup_interval: 7        # 全量备份频率（天）
    incremental_backup_interval: 24 # 增量备份频率（小时）
  retention:
    full_backup_count: 4           # 全量备份保留数量
    incremental_backup_count: 7    # 增量备份保留数量
    max_days: 30                   # 最长保留天数
```

### 目标命名空间

```yaml
namespaces: []
  # - default
  # - app-production
```

### 排除规则

```yaml
exclude:
  namespaces: []
    # - kube-system
  labels: []
    # - backup-enabled=false
  pvc_patterns: []
    # - "^tmp-.*"
```

### 通知配置

```yaml
email:
  enabled: false
  smtp_host: "smtp.example.com"
  to_addresses:
    - "admin@example.com"

webhook:
  enabled: false
  url: "https://hooks.example.com/backup"
```

## 📊 支持的应用类型

| 应用类型 | 备份方式 | 脚本 | 示例文档 |
|---------|---------|------|---------|
| MySQL | mysqldump + binlog | [mysql-backup.sh](scripts/mysql-backup.sh) | [mysql-backup.md](examples/mysql-backup.md) |
| PostgreSQL | pg_dump/pg_dumpall | [postgresql-backup.sh](scripts/postgresql-backup.sh) | [postgresql-backup.md](examples/postgresql-backup.md) |
| Redis | RDB/AOF | [redis-backup.sh](scripts/redis-backup.sh) | 待补充 |
| MinIO | mc mirror | [minio-backup.sh](scripts/minio-backup.sh) | 待补充 |
| 通用 PVC | rsync/tar/snapshot | [pvc-backup.sh](scripts/pvc-backup.sh) | [pvc-backup.md](examples/pvc-backup.md) |

## 🔒 离线环境部署

在离线环境中使用:

1. **提前下载脚本**:
   ```bash
   # 在有网络的环境下载
   git clone https://github.com/your-repo/backup.git
   # 复制到离线环境
   ```

2. **导入容器镜像**:
   ```bash
   # 导出镜像
   docker save mysql:8.0 postgres:15 alpine:latest -o backup-images.tar

   # 在离线环境导入
   docker load -i backup-images.tar
   ```

3. **使用本地脚本**:
   ```yaml
   volumeMounts:
   - name: local-scripts
     mountPath: /scripts
   volumes:
   - name: local-scripts
     hostPath:
       path: /opt/backup-scripts
   ```

## 🧪 测试

```bash
# 运行应用发现测试
python -m pytest tests/test_discovery.py

# 手动测试发现功能
python src/discovery/__init__.py
```

## 📝 开发计划

- [ ] 实现配置提取模块 (`src/extractor/`)
- [ ] 实现模板渲染模块 (`src/renderer/`)
- [ ] 实现主程序逻辑 (`src/main.py`)
- [ ] 添加单元测试
- [ ] 添加 Dockerfile
- [ ] 添加 Helm Chart
- [ ] 支持 Web UI
- [ ] 支持 Prometheus 监控

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📄 License

MIT License
