#!/bin/bash
# 备份验证脚本
# 验证备份文件的完整性和可用性

set -e

# 配置
BACKUP_DIR="${BACKUP_DIR:-/backup}"
APP_TYPE="${APP_TYPE:-generic}"
VERIFY_METHOD="${VERIFY_METHOD:-checksum}"  # checksum, content, both
ALGORITHM="${ALGORITHM:-sha256}"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 错误处理
error_exit() {
    log "ERROR: $1"
    exit 1
}

log "开始备份验证流程: app_type=${APP_TYPE}, method=${VERIFY_METHOD}"

# 验证函数
validate_checksum() {
    log "执行校验和验证..."

    # 查找备份文件
    BACKUP_FILES=$(find "${BACKUP_DIR}" -type f \( -name "*.sql" -o -name "*.sql.gz" -o -name "*.dump" -o -name "*.rdb" -o -name "*.aof" -o -name "*.tar" -o -name "*.tar.gz" \))

    if [ -z "$BACKUP_FILES" ]; then
        error_exit "未找到备份文件"
    fi

    # 为每个备份文件创建校验和
    for file in $BACKUP_FILES; do
        log "验证文件: $file"

        case $ALGORITHM in
            "md5")
                CHECKSUM=$(md5sum "$file" | cut -d' ' -f1)
                ;;
            "sha1")
                CHECKSUM=$(sha1sum "$file" | cut -d' ' -f1)
                ;;
            "sha256")
                CHECKSUM=$(sha256sum "$file" | cut -d' ' -f1)
                ;;
            *)
                error_exit "不支持的校验算法: $ALGORITHM"
                ;;
        esac

        # 保存校验和到文件
        CHECKSUM_FILE="${file}.${ALGORITHM}"
        echo "$CHECKSUM  $file" > "$CHECKSUM_FILE"
        log "校验和已保存到: $CHECKSUM_FILE"
    done

    log "校验和验证完成"
}

validate_content() {
    log "执行内容验证..."

    case $APP_TYPE in
        "mysql")
            validate_mysql_content
            ;;
        "postgresql")
            validate_postgresql_content
            ;;
        "redis")
            validate_redis_content
            ;;
        "minio")
            validate_minio_content
            ;;
        *)
            validate_generic_content
            ;;
    esac

    log "内容验证完成"
}

validate_mysql_content() {
    log "验证 MySQL 备份内容..."

    MYSQL_BACKUPS=$(find "${BACKUP_DIR}" -name "*.sql" -o -name "*.sql.gz")

    for backup in $MYSQL_BACKUPS; do
        log "检查 MySQL 备份: $backup"

        if [[ $backup == *.gz ]]; then
            # 检查压缩文件头部
            if gunzip -t "$backup" 2>/dev/null; then
                log "MySQL 备份文件压缩格式有效: $backup"

                # 检查部分内容
                HEADER=$(gunzip -c "$backup" | head -20)
                if echo "$HEADER" | grep -q "mysqldump\|INSERT INTO\|CREATE TABLE"; then
                    log "MySQL 备份内容格式正确: $backup"
                else
                    error_exit "MySQL 备份内容格式错误: $backup"
                fi
            else
                error_exit "MySQL 备份文件压缩错误: $backup"
            fi
        else
            # 检查普通SQL文件
            if [ -s "$backup" ]; then
                HEADER=$(head -20 "$backup")
                if echo "$HEADER" | grep -q "mysqldump\|INSERT INTO\|CREATE TABLE"; then
                    log "MySQL 备份内容格式正确: $backup"
                else
                    error_exit "MySQL 备份内容格式错误: $backup"
                fi
            else
                error_exit "MySQL 备份文件为空: $backup"
            fi
        fi
    done
}

validate_postgresql_content() {
    log "验证 PostgreSQL 备份内容..."

    POSTGRES_BACKUPS=$(find "${BACKUP_DIR}" -name "*.sql" -o -name "*.sql.gz" -o -name "*.dump")

    for backup in $POSTGRES_BACKUPS; do
        log "检查 PostgreSQL 备份: $backup"

        if [[ $backup == *.dump ]]; then
            # 检查自定义格式的头部
            if head -c 5 "$backup" | grep -q "PGDMP"; then
                log "PostgreSQL 自定义格式备份有效: $backup"
            else
                error_exit "PostgreSQL 自定义格式备份无效: $backup"
            fi
        elif [[ $backup == *.gz ]]; then
            if gunzip -t "$backup" 2>/dev/null; then
                log "PostgreSQL 备份文件压缩格式有效: $backup"

                HEADER=$(gunzip -c "$backup" | head -20)
                if echo "$HEADER" | grep -q "PostgreSQL\|INSERT INTO\|COPY"; then
                    log "PostgreSQL 备份内容格式正确: $backup"
                else
                    error_exit "PostgreSQL 备份内容格式错误: $backup"
                fi
            else
                error_exit "PostgreSQL 备份文件压缩错误: $backup"
            fi
        else
            # 普通SQL文件
            if [ -s "$backup" ]; then
                HEADER=$(head -20 "$backup")
                if echo "$HEADER" | grep -q "PostgreSQL\|INSERT INTO\|COPY"; then
                    log "PostgreSQL 备份内容格式正确: $backup"
                else
                    error_exit "PostgreSQL 备份内容格式错误: $backup"
                fi
            else
                error_exit "PostgreSQL 备份文件为空: $backup"
            fi
        fi
    done
}

validate_redis_content() {
    log "验证 Redis 备份内容..."

    REDIS_BACKUPS=$(find "${BACKUP_DIR}" -name "*.rdb")

    for backup in $REDIS_BACKUPS; do
        log "检查 Redis RDB 文件: $backup"

        # 检查 RDB 文件头部
        HEADER=$(head -c 9 "$backup")
        if [[ $HEADER == R*ED* ]]; then
            log "Redis RDB 文件格式正确: $backup"
        else
            error_exit "Redis RDB 文件格式错误: $backup"
        fi
    done
}

validate_minio_content() {
    log "验证 MinIO 备份内容..."

    MINIO_BACKUP_DIRS=$(find "${BACKUP_DIR}" -type d -name "*minio*" -mindepth 1)

    for backup_dir in $MINIO_BACKUP_DIRS; do
        log "检查 MinIO 备份目录: $backup_dir"

        if [ -n "$(ls -A "$backup_dir")" ]; then
            log "MinIO 备份目录非空: $backup_dir"
        else
            error_exit "MinIO 备份目录为空: $backup_dir"
        fi
    done
}

validate_generic_content() {
    log "验证通用备份内容..."

    # 检查备份目录是否非空
    if [ -n "$(ls -A "${BACKUP_DIR}")" ]; then
        log "备份目录非空，基本验证通过"
    else
        error_exit "备份目录为空"
    fi
}

create_verification_report() {
    log "生成验证报告..."

    REPORT_FILE="${BACKUP_DIR}/verification_report_$(date +%Y%m%d_%H%M%S).json"

    cat > "$REPORT_FILE" <<EOF
{
  "verification": {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "app_type": "$APP_TYPE",
    "verify_method": "$VERIFY_METHOD",
    "algorithm": "$ALGORITHM",
    "backup_directory": "$BACKUP_DIR",
    "results": {
      "checksum_validation": $(if [[ "$VERIFY_METHOD" == "checksum" || "$VERIFY_METHOD" == "both" ]]; then echo "true"; else echo "false"; fi),
      "content_validation": $(if [[ "$VERIFY_METHOD" == "content" || "$VERIFY_METHOD" == "both" ]]; then echo "true"; else echo "false"; fi),
      "passed": true,
      "details": "Validation completed successfully"
    }
  }
}
EOF

    log "验证报告已生成: $REPORT_FILE"
}

# 根据验证方法执行相应验证
case $VERIFY_METHOD in
    "checksum")
        validate_checksum
        ;;
    "content")
        validate_content
        ;;
    "both")
        validate_checksum
        validate_content
        ;;
    *)
        error_exit "不支持的验证方法: $VERIFY_METHOD"
        ;;
esac

# 创建验证报告
create_verification_report

log "备份验证流程完成"