#!/bin/bash
# 通用 PVC 数据备份脚本
# 使用 rsync 或 tar 备份 PVC 中的数据

set -e

# 配置
SOURCE_DIR="${SOURCE_DIR:-/data}"          # 要备份的源目录（PVC 挂载点）
BACKUP_DIR="${BACKUP_DIR:-/backup}"        # 备份目标目录
BACKUP_METHOD="${BACKUP_METHOD:-rsync}"    # 备份方法: rsync, tar, or snapshot
INCLUDE_PATTERNS="${INCLUDE_PATTERNS}"     # 要包含的文件模式（用空格分隔）
EXCLUDE_PATTERNS="${EXCLUDE_PATTERNS}"     # 要排除的文件模式（用空格分隔）
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

# 应用名称（用于命名备份文件）
APP_NAME="${APP_NAME:-pvc-backup}"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 错误处理
error_exit() {
    log "ERROR: $1"
    exit 1
}

log "开始备份: method=${BACKUP_METHOD}, source=${SOURCE_DIR}, app=${APP_NAME}"

# 构建 rsync exclude 参数
RSYNC_EXCLUDE=""
if [ -n "${EXCLUDE_PATTERNS}" ]; then
    for pattern in ${EXCLUDE_PATTERNS}; do
        RSYNC_EXCLUDE="${RSYNC_EXCLUDE} --exclude='${pattern}'"
    done
fi

if [ "${BACKUP_METHOD}" = "rsync" ]; then
    # 使用 rsync 增量备份
    DEST_DIR="${BACKUP_DIR}/${APP_NAME}_$(date +%Y%m%d)"

    log "使用 rsync 备份到: ${DEST_DIR}"

    mkdir -p "${DEST_DIR}"

    # 执行 rsync
    eval rsync -av --delete ${RSYNC_EXCLUDE} "${SOURCE_DIR}/" "${DEST_DIR}/"

    log "rsync 备份完成"
    echo "${DEST_DIR}"

elif [ "${BACKUP_METHOD}" = "tar" ]; then
    # 使用 tar 打包备份
    BACKUP_FILE="${BACKUP_DIR}/${APP_NAME}_${TIMESTAMP}.tar.gz"

    log "使用 tar 打包备份到: ${BACKUP_FILE}"

    # 构建 tar exclude 参数
    TAR_EXCLUDE=""
    if [ -n "${EXCLUDE_PATTERNS}" ]; then
        for pattern in ${EXCLUDE_PATTERNS}; do
            TAR_EXCLUDE="${TAR_EXCLUDE} --exclude='${pattern}'"
        done
    fi

    # 执行 tar
    cd "${SOURCE_DIR}"
    eval tar -czf "${BACKUP_FILE}" ${TAR_EXCLUDE} .

    log "tar 备份完成: ${BACKUP_FILE}"
    echo "${BACKUP_FILE}"

elif [ "${BACKUP_METHOD}" = "snapshot" ]; then
    # 使用 VolumeSnapshot（需要 Kubernetes CSI 支持）
    # 这个方法需要通过 Kubernetes API 创建 VolumeSnapshot 资源
    # 脚本只生成 YAML，需要外部工具应用
    log "生成 VolumeSnapshot YAML"

    SNAPSHOT_NAME="${APP_NAME}-snapshot-${TIMESTAMP}"
    PVC_NAME="${PVC_NAME}"
    SNAPSHOT_CLASS="${SNAPSHOT_CLASS:-default}"

    SNAPSHOT_YAML="${BACKUP_DIR}/${SNAPSHOT_NAME}.yaml"

    cat > "${SNAPSHOT_YAML}" <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: ${SNAPSHOT_NAME}
spec:
  volumeSnapshotClassName: ${SNAPSHOT_CLASS}
  source:
    persistentVolumeClaimName: ${PVC_NAME}
EOF

    log "VolumeSnapshot YAML 已生成: ${SNAPSHOT_YAML}"
    echo "${SNAPSHOT_YAML}"

else
    error_exit "未知的备份方法: ${BACKUP_METHOD}"
fi

# 清理旧备份
if [ -n "${RETENTION_DAYS}" ]; then
    log "清理 ${RETENTION_DAYS} 天前的旧备份"

    if [ "${BACKUP_METHOD}" = "rsync" ]; then
        find "${BACKUP_DIR}" -type d -name "${APP_NAME}_*" -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
    else
        find "${BACKUP_DIR}" -name "${APP_NAME}_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
        find "${BACKUP_DIR}" -name "${APP_NAME}_*.yaml" -mtime +${RETENTION_DAYS} -delete
    fi
fi

log "备份脚本执行完成"
