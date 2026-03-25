# 安全加固说明

**更新日期**: 2026-03-25
**版本**: v0.1.1

---

## 🔒 本次安全修复内容

### 1. 修复密码泄露问题 ✅

#### 问题描述
备份脚本通过命令行参数直接传递密码，导致密码可能泄露到进程列表中。

#### 影响范围
- [scripts/mysql-backup.sh](../scripts/mysql-backup.sh)
- [scripts/postgresql-backup.sh](../scripts/postgresql-backup.sh)
- [scripts/redis-backup.sh](../scripts/redis-backup.sh)
- [scripts/minio-backup.sh](../scripts/minio-backup.sh)

#### 修复方案

##### MySQL 备份脚本
```bash
# 修复前 - 密码暴露在进程列表
mysqldump --password=${MYSQL_PASSWORD} ...

# 修复后 - 使用临时配置文件
MYSQL_CONFIG_FILE=$(mktemp)
chmod 600 "${MYSQL_CONFIG_FILE}"
cat > "${MYSQL_CONFIG_FILE}" <<EOF
[client]
password=${MYSQL_PASSWORD}
EOF
mysqldump --defaults-extra-file=${MYSQL_CONFIG_FILE} ...
trap "rm -f ${MYSQL_CONFIG_FILE}" EXIT INT TERM
```

**关键点**:
- 使用 `--defaults-extra-file` 避免命令行暴露密码
- 临时文件权限设置为 `600`（仅所有者可读写）
- 使用 `trap` 确保脚本退出时自动清理临时文件

##### PostgreSQL 备份脚本
```bash
# 修复前 - 使用 PGPASSWORD 环境变量（仍有风险）
export PGPASSWORD="${PGPASSWORD}"

# 修复后 - 使用 .pgpass 文件
PGPASS_FILE=$(mktemp)
chmod 600 "${PGPASS_FILE}"
cat > "${PGPASS_FILE}" <<EOF
${PGHOST}:${PGPORT}:${PGDATABASE:-*}:${PGUSER}:${PGPASSWORD}
EOF
export PGPASSFILE="${PGPASS_FILE}"
trap "rm -f ${PGPASS_FILE}" EXIT INT TERM
```

**关键点**:
- 使用 `.pgpass` 文件替代环境变量
- 文件权限 `600`
- 自动清理

##### Redis 备份脚本
```bash
# 修复前 - 密码在命令行参数中
redis-cli -a ${REDIS_PASSWORD} ...

# 修复后 - 使用 REDISCLI_AUTH 环境变量
export REDISCLI_AUTH="${REDIS_PASSWORD}"
redis-cli ...
```

**关键点**:
- 使用专用环境变量 `REDISCLI_AUTH`
- 避免 `-a` 参数暴露密码

##### MinIO 备份脚本
```bash
# 修复前 - 密钥在命令行中
mc alias set ${MC_ALIAS} "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" ...

# 修复后 - 使用环境变量传递（配合命令）
MC_ACCESS_KEY="${MINIO_ACCESS_KEY}" MC_SECRET_KEY="${MINIO_SECRET_KEY}" \
mc alias set ${MC_ALIAS} "${MINIO_ENDPOINT}" ...
```

---

### 2. 修复 RBAC 权限过大问题 ✅

#### 问题描述
ServiceAccount 被授予了过多的权限，违反了最小权限原则。

#### 修复内容

##### 权限调整
**修改文件**: [deploy/helm/k8s-backup-manager/values.yaml](../deploy/helm/k8s-backup-manager/values.yaml)

```yaml
# 修复前
rules:
  - apiGroups: [""]
    resources: ["persistentvolumeclaims", "persistentvolumes"]
    verbs: ["get", "list", "watch", "create"]  # 过多权限
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]  # 过多权限

# 修复后
rules:
  # 只读权限：应用发现
  - apiGroups: [""]
    resources: ["pods", "namespaces"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["persistentvolumeclaims", "persistentvolumes"]
    verbs: ["get", "list", "watch"]  # 移除 create
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets", "daemonsets", "replicasets"]
    verbs: ["get", "list", "watch"]

  # 写入权限：仅限备份相关资源
  - apiGroups: ["batch"]
    resources: ["jobs"]  # 移除 cronjobs（可选功能）
    verbs: ["get", "list", "watch", "create"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets", "persistentvolumeclaims"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["snapshot.storage.k8s.io"]
    resources: ["volumesnapshots", "volumesnapshotcontents"]
    verbs: ["get", "list", "watch", "create", "delete"]
```

**关键改进**:
- 移除了对核心工作负载（Deployment/StatefulSet）的写权限
- 移除了不必要的 `update`、`patch`、`delete` 权限
- 添加了注释说明每个权限的用途
- 增加了 `replicasets` 的读取权限（支持更多资源类型）

##### 禁用 ServiceAccount Token 自动挂载

**修改文件**: [deploy/helm/k8s-backup-manager/templates/serviceaccount.yaml](../deploy/helm/k8s-backup-manager/templates/serviceaccount.yaml)

```yaml
# 修复前
automountServiceAccountToken: true

# 修复后
automountServiceAccountToken: false
```

**说明**:
- 默认不挂载 ServiceAccount token，减少攻击面
- 使用时在 Pod 中按需挂载

---

### 3. 移除硬编码密码 ✅

#### 问题描述
Secret 模板中包含示例密码（`your-password`），可能误导用户直接使用。

#### 修复内容

**修改文件**: [src/renderer/__init__.py](../src/renderer/__init__.py)

```python
# 修复前
secret_data['MYSQL_PASSWORD'] = 'your-password'  # 用户需要修改

# 修复后
secret_data['MYSQL_PASSWORD'] = 'CHANGE_ME'  # TODO: Replace with actual password
```

**添加警告注释**:
```yaml
# WARNING: This Secret contains placeholder values
# Replace all 'CHANGE_ME' values with actual secrets before applying
# Example: kubectl create secret generic {name} --from-literal=MYSQL_PASSWORD='actual-password' -n {namespace}
```

**关键点**:
- 使用 `CHANGE_ME` 明确标识需要修改
- 在 Secret 中添加警告注释
- 添加 `kubernetes.io/description` 注解
- 提供创建 Secret 的示例命令

---

## 📋 安全最佳实践

### 1. 密码管理

#### 推荐做法
```bash
# 使用 kubectl create secret
kubectl create secret generic mysql-backup-secret \
  --from-literal=MYSQL_PASSWORD='your-secure-password' \
  -n database

# 或使用文件
echo -n 'your-password' > ./password.txt
kubectl create secret generic mysql-backup-secret \
  --from-file=MYSQL_PASSWORD=./password.txt \
  -n database
```

#### 不推荐做法
```bash
# ❌ 避免在命令行中直接写密码
kubectl create secret generic mysql-backup-secret \
  --from-literal=MYSQL_PASSWORD='password123'

# ❌ 避免在 YAML 中硬编码密码
apiVersion: v1
kind: Secret
metadata:
  name: mysql-backup-secret
stringData:
  MYSQL_PASSWORD: password123  # 明文密码
```

---

### 2. RBAC 最小权限原则

#### 原则
- **只授予必要的权限**
- **定期审计权限使用情况**
- **使用命名空间级别权限，避免集群级别**

#### 检查权限使用
```bash
# 查看 ServiceAccount 的权限
kubectl auth can-i --list --as=system:serviceaccount:backup:k8s-backup-manager -n backup

# 测试特定权限
kubectl auth can-i create jobs --as=system:serviceaccount:backup:k8s-backup-manager -n backup
```

---

### 3. 备份脚本安全

#### 环境变量安全
```bash
# ✅ 使用 Secret 挂载环境变量
env:
  - name: MYSQL_PASSWORD
    valueFrom:
      secretKeyRef:
        name: mysql-backup-secret
        key: MYSQL_PASSWORD
```

#### 文件权限
```bash
# 确保临时文件权限正确
chmod 600 /tmp/.mysql_pass  # 仅所有者可读写
chmod 644 /tmp/config.yaml   # 所有者可读写，其他只读
```

#### 审计日志
```bash
# 启用 Kubernetes 审计日志
# 记录所有 Secret 访问和 Pod 创建事件
```

---

## 🧪 安全测试

### 1. 验证密码不在进程列表中
```bash
# 运行备份脚本
./scripts/mysql-backup.sh &

# 检查进程参数（不应包含密码）
ps aux | grep mysqldump

# 应该看不到 --password=xxx 或明文密码
```

### 2. 验证临时文件清理
```bash
# 运行脚本后检查临时文件
ls -la /tmp/ | grep mysql

# 临时文件应该已被删除
```

### 3. 验证 RBAC 权限
```bash
# 测试 ServiceAccount 权限
kubectl auth can-i create deployments \
  --as=system:serviceaccount:backup:k8s-backup-manager -n backup
# 应该返回 no

kubectl auth can-i create jobs \
  --as=system:serviceaccount:backup:k8s-backup-manager -n backup
# 应该返回 yes
```

---

## 🔍 已知安全限制

1. **环境变量仍可能被读取**
   - 虽然不暴露在命令行，但环境变量仍可被容器内进程读取
   - 建议使用 Secret 挂载到文件，而不是环境变量

2. **临时文件路径可预测**
   - `mktemp` 生成的路径有一定可预测性
   - 建议在高安全环境中使用更安全的临时文件机制

3. **脚本执行权限**
   - 备份脚本需要执行权限，可能被恶意修改
   - 建议使用只读 ConfigMap 挂载脚本

---

## 📚 相关资源

- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [Secrets Management](https://kubernetes.io/docs/concepts/configuration/secret/)
- [RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

---

**下一步**: 建议进行安全审计和渗透测试，确保没有其他安全漏洞。
