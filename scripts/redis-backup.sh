#!/bin/bash
# Redis 备份脚本
# 支持 RDB 和 AOF 备份

set -e

# 配置
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD}"
BACKUP_DIR="${BACKUP_DIR:-/backup/redis}"
BACKUP_TYPE="${BACKUP_TYPE:-rdb}"  # rdb 或 aof
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

# 检查 redis-cli 是否存在
if ! command -v redis-cli &> /dev/null; then
    error_exit "redis-cli 命令未找到，请安装 Redis 客户端"
fi

log "开始 Redis 备份: type=${BACKUP_TYPE}, host=${REDIS_HOST}:${REDIS_PORT}"

# 构建 redis-cli 参数
REDIS_CLI_OPTS="-h ${REDIS_HOST} -p ${REDIS_PORT}"
if [ -n "${REDIS_PASSWORD}" ]; then
    REDIS_CLI_OPTS="${REDIS_CLI_OPTS} -a ${REDIS_PASSWORD} --no-auth-warning"
fi

if [ "${BACKUP_TYPE}" = "rdb" ]; then
    # RDB 备份
    # 触发 BGSAVE
    log "触发 BGSAVE..."
    redis-cli ${REDIS_CLI_OPTS} BGSAVE

    # 等待 RDB 保存完成
    sleep 2

    # 获取 RDB 文件路径
    RDB_PATH=$(redis-cli ${REDIS_CLI_OPTS} CONFIG GET dir | grep -A1 dir | tail -1)
    RDB_FILE=$(redis-cli ${REDIS_CLI_OPTS} CONFIG GET dbfilename | grep -A1 dbfilename | tail -1)

    if [ -f "${RDB_PATH}/${RDB_FILE}" ]; then
        BACKUP_FILE="${BACKUP_DIR}/redis_rdb_${TIMESTAMP}.rdb"
        cp "${RDB_PATH}/${RDB_FILE}" "${BACKUP_FILE}"
        log "RDB 备份完成: ${BACKUP_FILE}"
        echo "${BACKUP_FILE}"
    else
        error_exit "RDB 文件不存在: ${RDB_PATH}/${RDB_FILE}"
    fi

elif [ "${BACKUP_TYPE}" = "aof" ]; then
    # AOF 备份
    # 触发 BGREWRITEAOF
    log "触发 BGREWRITEAOF..."
    redis-cli ${REDIS_CLI_OPTS} BGREWRITEAOF

    # 等待 AOF 重写完成
    sleep 2

    # 获取 AOF 文件路径
    AOF_PATH=$(redis-cli ${REDIS_CLI_OPTS} CONFIG GET dir | grep -A1 dir | tail -1)
    AOF_FILE=$(redis-cli ${REDIS_CLI_OPTS} CONFIG GET appendfilename | grep -A1 appendfilename | tail -1)

    if [ -f "${AOF_PATH}/${AOF_FILE}" ]; then
        BACKUP_FILE="${BACKUP_DIR}/redis_aof_${TIMESTAMP}.aof"
        cp "${AOF_PATH}/${AOF_FILE}" "${BACKUP_FILE}"
        log "AOF 备份完成: ${BACKUP_FILE}"
        echo "${BACKUP_FILE}"
    else
        error_exit "AOF 文件不存在: ${AOF_PATH}/${AOF_FILE}"
    fi

else
    error_exit "未知的备份类型: ${BACKUP_TYPE}"
fi

# 清理旧备份
if [ -n "${RETENTION_DAYS}" ]; then
    log "清理 ${RETENTION_DAYS} 天前的旧备份"
    find "${BACKUP_DIR}" -name "redis_*.rdb" -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -name "redis_*.aof" -mtime +${RETENTION_DAYS} -delete
fi

log "备份脚本执行完成"
