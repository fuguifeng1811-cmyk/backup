#!/bin/bash
# MinIO/对象存储备份脚本
# 将对象存储数据同步到本地或其他存储

set -e

# 配置
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY}"
MINIO_BUCKET="${MINIO_BUCKET}"              # 要备份的 bucket，留空则备份所有 bucket
BACKUP_DIR="${BACKUP_DIR:-/backup/minio}"
MC_ALIAS="${MC_ALIAS:-backup}"

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 错误处理
error_exit() {
    log "ERROR: $1"
    exit 1
}

# 检查 mc (MinIO Client) 是否存在
if ! command -v mc &> /dev/null; then
    error_exit "mc 命令未找到，请安装 MinIO Client: https://min.io/download#/linux"
fi

log "开始 MinIO 备份: endpoint=${MINIO_ENDPOINT}, bucket=${MINIO_BUCKET:-all}"

# 配置 mc alias
log "配置 MinIO 连接..."
mc alias set ${MC_ALIAS} "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --api S3v4

# 获取所有 bucket 列表
if [ -z "${MINIO_BUCKET}" ]; then
    BUCKETS=$(mc ls ${MC_ALIAS} | awk '{print $5}')
else
    BUCKETS="${MINIO_BUCKET}"
fi

log "发现 buckets: ${BUCKETS}"

# 备份每个 bucket
for bucket in ${BUCKETS}; do
    log "备份 bucket: ${bucket}"

    BUCKET_BACKUP_DIR="${BACKUP_DIR}/${bucket}"
    mkdir -p "${BUCKET_BACKUP_DIR}"

    # 使用 mc mirror 同步（增量备份）
    mc mirror ${MC_ALIAS}/${bucket} "${BUCKET_BACKUP_DIR}"

    log "Bucket ${bucket} 备份完成"
done

# 创建备份清单
BACKUP_MANIFEST="${BACKUP_DIR}/backup_manifest_$(date +%Y%m%d_%H%M%S).txt"
log "生成备份清单: ${BACKUP_MANIFEST}"

cat > "${BACKUP_MANIFEST}" <<EOF
MinIO Backup Manifest
=====================
备份时间: $(date +'%Y-%m-%d %H:%M:%S')
源地址: ${MINIO_ENDPOINT}
备份目录: ${BACKUP_DIR}

备份的 Buckets:
EOF

for bucket in ${BUCKETS}; do
    SIZE=$(du -sh "${BACKUP_DIR}/${bucket}" 2>/dev/null | cut -f1)
    echo "- ${bucket}: ${SIZE}" >> "${BACKUP_MANIFEST}"
done

log "备份清单已生成"
echo "${BACKUP_MANIFEST}"

# 清理旧备份
if [ -n "${RETENTION_DAYS}" ]; then
    log "清理 ${RETENTION_DAYS} 天前的旧备份"
    find "${BACKUP_DIR}" -name "backup_manifest_*.txt" -mtime +${RETENTION_DAYS} -delete

    # 注意：这里只删除清单文件，实际数据保留策略应单独配置
fi

log "备份脚本执行完成"
