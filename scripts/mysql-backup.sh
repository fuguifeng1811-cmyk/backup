#!/bin/bash
# MySQL 备份脚本
# 支持全量备份和 binlog 备份

set -e

# 配置
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD}"
MYSQL_DATABASE="${MYSQL_DATABASE}"
BACKUP_DIR="${BACKUP_DIR:-/backup/mysql}"
BACKUP_TYPE="${BACKUP_TYPE:-full}"  # full 或 binlog
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

# 检查 mysqldump 是否存在
if ! command -v mysqldump &> /dev/null; then
    error_exit "mysqldump 命令未找到，请安装 MySQL 客户端"
fi

# 构建 MySQL 连接参数
MYSQL_OPTS="--host=${MYSQL_HOST} --port=${MYSQL_PORT} --user=${MYSQL_USER}"
if [ -n "${MYSQL_PASSWORD}" ]; then
    MYSQL_OPTS="${MYSQL_OPTS} --password=${MYSQL_PASSWORD}"
fi

log "开始 MySQL 备份: type=${BACKUP_TYPE}, database=${MYSQL_DATABASE:-all}"

if [ "${BACKUP_TYPE}" = "full" ]; then
    # 全量备份
    BACKUP_FILE="${BACKUP_DIR}/mysql_full_${MYSQL_DATABASE:-all}_${TIMESTAMP}.sql.gz"

    log "执行全量备份到: ${BACKUP_FILE}"

    if [ -n "${MYSQL_DATABASE}" ]; then
        # 备份指定数据库
        mysqldump ${MYSQL_OPTS} \
            --single-transaction \
            --quick \
            --lock-tables=false \
            --routines \
            --triggers \
            --events \
            "${MYSQL_DATABASE}" | gzip > "${BACKUP_FILE}"
    else
        # 备份所有数据库
        mysqldump ${MYSQL_OPTS} \
            --single-transaction \
            --quick \
            --lock-tables=false \
            --routines \
            --triggers \
            --events \
            --all-databases | gzip > "${BACKUP_FILE}"
    fi

    log "全量备份完成: ${BACKUP_FILE}"
    echo "${BACKUP_FILE}"

elif [ "${BACKUP_TYPE}" = "binlog" ]; then
    # Binlog 备份
    # 需要先刷新 binlog
    mysql ${MYSQL_OPTS} -e "FLUSH LOGS;"

    # 获取当前 binlog 位置
    BINLOG_FILE=$(mysql ${MYSQL_OPTS} -NBe "SHOW MASTER STATUS" | awk '{print $1}')

    log "当前 binlog 文件: ${BINLOG_FILE}"

    # 复制 binlog 文件（需要 MySQL 数据目录权限）
    # 这里假设可以访问 /var/lib/mysql
    if [ -f "/var/lib/mysql/${BINLOG_FILE}" ]; then
        BINLOG_BACKUP="${BACKUP_DIR}/mysql_binlog_${BINLOG_FILE}_${TIMESTAMP}.gz"
        gzip -c "/var/lib/mysql/${BINLOG_FILE}" > "${BINLOG_BACKUP}"
        log "Binlog 备份完成: ${BINLOG_BACKUP}"
        echo "${BINLOG_BACKUP}"
    else
        error_exit "无法访问 binlog 文件: /var/lib/mysql/${BINLOG_FILE}"
    fi

else
    error_exit "未知的备份类型: ${BACKUP_TYPE}"
fi

# 清理旧备份（保留最近 7 天）
if [ -n "${RETENTION_DAYS}" ]; then
    log "清理 ${RETENTION_DAYS} 天前的旧备份"
    find "${BACKUP_DIR}" -name "mysql_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -name "mysql_binlog_*.gz" -mtime +${RETENTION_DAYS} -delete
fi

log "备份脚本执行完成"
