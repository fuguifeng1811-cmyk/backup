#!/bin/bash
# 通用备份并上传到远程存储脚本
# 支持本地备份后上传到 S3 兼容存储

set -e

# 配置
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-/backup/local}"
REMOTE_STORAGE_TYPE="${REMOTE_STORAGE_TYPE:-none}"  # none, s3
S3_ENDPOINT="${S3_ENDPOINT}"
S3_ACCESS_KEY="${S3_ACCESS_KEY}"
S3_SECRET_KEY="${S3_SECRET_KEY}"
S3_BUCKET="${S3_BUCKET}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 错误处理
error_exit() {
    log "ERROR: $1"
    exit 1
}

log "开始备份和远程上传流程"

# 创建本地备份目录
mkdir -p "${LOCAL_BACKUP_DIR}"

# 如果启用了 S3 存储，则上传文件
if [ "${REMOTE_STORAGE_TYPE}" = "s3" ]; then
    log "检测到 S3 存储配置，开始上传备份文件..."

    # 检查 aws cli 是否存在
    if ! command -v aws &> /dev/null; then
        log "安装 AWS CLI..."
        apk add --no-cache python3 py3-pip curl unzip groff
        # 安装 AWS CLI v2
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
        unzip awscliv2.zip
        ./aws/install
        rm awscliv2.zip
        rm -rf aws/
    fi

    # 配置 AWS CLI
    AWS_CONFIG_FILE=$(mktemp)
    chmod 600 "${AWS_CONFIG_FILE}"
    cat > "${AWS_CONFIG_FILE}" <<EOF
[default]
s3 =
    signature_version = s3v4
EOF

    AWS_CREDENTIALS_FILE=$(mktemp)
    chmod 600 "${AWS_CREDENTIALS_FILE}"
    cat > "${AWS_CREDENTIALS_FILE}" <<EOF
[default]
aws_access_key_id = ${S3_ACCESS_KEY}
aws_secret_access_key = ${S3_SECRET_KEY}
EOF

    export AWS_CONFIG_FILE="${AWS_CONFIG_FILE}"
    export AWS_SHARED_CREDENTIALS_FILE="${AWS_CREDENTIALS_FILE}"

    # 设置 AWS 端点（如果使用非 AWS S3）
    if [[ "${S3_ENDPOINT}" == *"amazonaws"* ]]; then
        AWS_ARGS=""
    else
        AWS_ARGS="--endpoint-url=${S3_ENDPOINT}"
    fi

    # 上传所有本地备份文件到 S3
    for file in "${LOCAL_BACKUP_DIR}"/*; do
        if [ -f "$file" ]; then
            log "上传 $file 到 S3..."
            FILE_NAME=$(basename "$file")
            aws s3 ${AWS_ARGS} cp "$file" "s3://${S3_BUCKET}/$FILE_NAME" || error_exit "上传 $file 失败"
        fi
    done

    # 清理临时文件
    rm -f "${AWS_CONFIG_FILE}" "${AWS_CREDENTIALS_FILE}"

    log "所有备份文件已成功上传到 S3"
else
    log "未配置远程存储，跳过上传步骤"
fi

# 清理本地旧备份
if [ -n "${BACKUP_RETENTION_DAYS}" ]; then
    log "清理 ${BACKUP_RETENTION_DAYS} 天前的本地备份文件"
    find "${LOCAL_BACKUP_DIR}" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete
fi

log "备份和上传流程完成"