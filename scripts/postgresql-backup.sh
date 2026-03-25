#!/bin/bash
# PostgreSQL 备份脚本
# 支持全量备份

set -e

# 配置
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD}"
PGDATABASE="${PGDATABASE}"
BACKUP_DIR="${BACKUP_DIR:-/backup/postgresql}"
BACKUP_FORMAT="${BACKUP_FORMAT:-custom}"  # custom, plain, directory, tar
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# 检查 pg_dump 是否存在
if ! command -v pg_dump &> /dev/null; then
    error_exit "pg_dump 命令未找到，请安装 PostgreSQL 客户端"
fi

log "开始 PostgreSQL 备份: format=${BACKUP_FORMAT}, database=${PGDATABASE:-all}"

# 构建 pg_dump 参数
PG_DUMP_OPTS="--host=${PGHOST} --port=${PGPORT} --username=${PGUSER}"

# 安全处理密码 - 使用 .pgpass 文件避免密码泄露
if [ -n "${PGPASSWORD}" ]; then
    # 创建临时 .pgpass 文件（仅当前用户可读）
    PGPASS_FILE=$(mktemp)
    chmod 600 "${PGPASS_FILE}"

    cat > "${PGPASS_FILE}" <<EOF
${PGHOST}:${PGPORT}:${PGDATABASE:-*}:${PGUSER}:${PGPASSWORD}
EOF

    export PGPASSFILE="${PGPASS_FILE}"

    # 确保临时文件在脚本退出时被删除
    trap "rm -f ${PGPASS_FILE}" EXIT INT TERM
fi

if [ -n "${PGDATABASE}" ]; then
    # 备份指定数据库
    if [ "${BACKUP_FORMAT}" = "custom" ]; then
        BACKUP_FILE="${BACKUP_DIR}/pg_${PGDATABASE}_${TIMESTAMP}.dump"
        log "执行自定义格式备份到: ${BACKUP_FILE}"
        pg_dump ${PG_DUMP_OPTS} \
            --format=custom \
            --blobs \
            --verbose \
            "${PGDATABASE}" > "${BACKUP_FILE}"
    elif [ "${BACKUP_FORMAT}" = "plain" ]; then
        BACKUP_FILE="${BACKUP_DIR}/pg_${PGDATABASE}_${TIMESTAMP}.sql.gz"
        log "执行 SQL 格式备份到: ${BACKUP_FILE}"
        pg_dump ${PG_DUMP_OPTS} \
            --format=plain \
            --blobs \
            --verbose \
            "${PGDATABASE}" | gzip > "${BACKUP_FILE}"
    else
        error_exit "不支持的备份格式: ${BACKUP_FORMAT}"
    fi
else
    # 备份所有数据库
    BACKUP_FILE="${BACKUP_DIR}/pg_all_${TIMESTAMP}.dump"
    log "执行全库备份到: ${BACKUP_FILE}"
    pg_dumpall ${PG_DUMP_OPTS} \
        --globals-only \
        --verbose > "${BACKUP_FILE}"
fi

log "备份完成: ${BACKUP_FILE}"
echo "${BACKUP_FILE}"

# 清理旧备份（保留最近 7 天）
if [ -n "${RETENTION_DAYS}" ]; then
    log "清理 ${RETENTION_DAYS} 天前的旧备份"
    find "${BACKUP_DIR}" -name "pg_*.dump" -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -name "pg_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
fi

log "备份脚本执行完成"
