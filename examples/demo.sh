#!/bin/bash
# K8s Backup Manager 使用示例脚本

set -e

echo "======================================"
echo "K8s Backup Manager - 使用示例"
echo "======================================"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 环境
echo -e "${YELLOW}检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}未找到 python3，尝试使用 python${NC}"
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

echo -e "${GREEN}✓ Python 可用${NC}"

# 1. 安装依赖
echo ""
echo -e "${YELLOW}1. 安装依赖...${NC}"
$PYTHON_CMD -m pip install -r requirements.txt

# 2. 配置文件
echo ""
echo -e "${YELLOW}2. 配置文件...${NC}"
if [ ! -f config.yaml ]; then
    echo "创建配置文件 config.yaml..."
    cp config.example.yaml config.yaml
    echo -e "${GREEN}✓ 配置文件已创建，请根据实际情况编辑 config.yaml${NC}"
else
    echo -e "${GREEN}✓ 配置文件已存在${NC}"
fi

# 3. 发现有状态应用
echo ""
echo -e "${YELLOW}3. 发现有状态应用...${NC}"
echo "运行: $PYTHON_CMD src/main.py discover"
echo ""
$PYTHON_CMD src/main.py discover || echo "提示: 需要配置 kubeconfig 才能连接 Kubernetes 集群"

# 4. 发现特定命名空间
echo ""
echo -e "${YELLOW}4. 发现特定命名空间的应用...${NC}"
echo "运行: $PYTHON_CMD src/main.py discover --namespace default"
echo ""
$PYTHON_CMD src/main.py discover --namespace default 2>/dev/null || echo "提示: 需要配置 kubeconfig"

# 5. 提取备份配置
echo ""
echo -e "${YELLOW}5. 提取备份配置...${NC}"
echo "运行: $PYTHON_CMD src/main.py extract"
echo ""
$PYTHON_CMD src/main.py extract 2>/dev/null || echo "提示: 需要配置 kubeconfig"

# 6. 生成备份清单
echo ""
echo -e "${YELLOW}6. 生成备份清单...${NC}"
echo "运行: $PYTHON_CMD src/main.py generate --output manifests/"
echo ""
$PYTHON_CMD src/main.py generate --output manifests/ 2>/dev/null || echo "提示: 需要配置 kubeconfig"

# 7. 查看生成的清单
echo ""
echo -e "${YELLOW}7. 查看生成的清单...${NC}"
if [ -d manifests ]; then
    echo "生成的清单文件:"
    ls -la manifests/
else
    echo "manifests/ 目录不存在（需要先运行 generate 命令）"
fi

# 8. 模块独立测试
echo ""
echo -e "${YELLOW}8. 测试各个模块...${NC}"

echo ""
echo "测试 discovery 模块:"
$PYTHON_CMD -m src.discovery 2>/dev/null || echo "提示: 需要配置 kubeconfig"

echo ""
echo "测试 extractor 模块:"
$PYTHON_CMD -m src.extractor

echo ""
echo "测试 renderer 模块:"
$PYTHON_CMD -m src.renderer

echo ""
echo "测试 utils 模块:"
$PYTHON_CMD -m src.utils

# 9. 帮助信息
echo ""
echo -e "${YELLOW}9. 查看帮助信息...${NC}"
$PYTHON_CMD src/main.py --help

echo ""
echo -e "${YELLOW}10. 查看 discover 命令帮助...${NC}"
$PYTHON_CMD src/main.py discover --help

echo ""
echo "======================================"
echo -e "${GREEN}示例脚本执行完成！${NC}"
echo "======================================"
echo ""
echo "下一步操作:"
echo "1. 编辑 config.yaml 配置你的环境"
echo "2. 配置 kubeconfig 连接 Kubernetes 集群"
echo "3. 运行: $PYTHON_CMD src/main.py discover"
echo "4. 运行: $PYTHON_CMD src/main.py generate"
echo ""
