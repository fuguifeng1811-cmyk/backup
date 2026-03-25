# 使用多阶段构建优化镜像大小
FROM python:3.11-slim as builder

WORKDIR /app

# 安装编译依赖（如果需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt


# 运行时镜像
FROM python:3.11-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    unzip \
    groff \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 安装 AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm awscliv2.zip \
    && rm -rf aws/

# 复制应用代码
COPY src/ ./src/
COPY scripts/ ./scripts/

# 创建非 root 用户
RUN useradd -m -u 1000 backup && \
    chown -R backup:backup /app

USER backup

# 默认命令：显示帮助信息
CMD ["python", "src/main.py", "--help"]
