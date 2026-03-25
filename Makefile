# Makefile - 容器化部署快捷命令

.PHONY: help build build-alpine push deploy-helm deploy-kustomize test clean

# 默认目标
help:
	@echo "K8s Backup Manager - 容器化部署"
	@echo ""
	@echo "可用命令:"
	@echo "  make build              - 构建 Docker 镜像"
	@echo "  make build-alpine       - 使用 Alpine 构建镜像（更小）"
	@echo "  make push               - 推送镜像到仓库"
	@echo "  make deploy-helm        - 使用 Helm 部署"
	@echo "  make deploy-kustomize   - 使用 Kustomize 部署"
	@echo "  make test               - 运行测试"
	@echo "  make clean              - 清理构建产物"
	@echo ""

# 镜像配置
IMAGE_NAME ?= k8s-backup-manager
IMAGE_TAG ?= 0.1.0
IMAGE_REGISTRY ?= your-registry
IMAGE := $(IMAGE_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

# 构建 Docker 镜像
build:
	@echo "📦 构建 Docker 镜像: $(IMAGE)"
	docker build -t $(IMAGE) .
	@echo "✅ 镜像构建完成: $(IMAGE)"

# 使用 Alpine 构建（更小的镜像）
build-alpine:
	@echo "📦 使用 Alpine 构建 Docker 镜像: $(IMAGE)"
	docker build -f Dockerfile.alpine -t $(IMAGE) .
	@echo "✅ 镜像构建完成: $(IMAGE)"

# 推送镜像到仓库
push:
	@echo "📤 推送镜像: $(IMAGE)"
	docker push $(IMAGE)
	@echo "✅ 镜像推送完成"

# 使用 Helm 部署
deploy-helm:
	@echo "🚀 使用 Helm 部署"
	helm upgrade --install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
		--namespace backup \
		--create-namespace \
		--wait
	@echo "✅ Helm 部署完成"

# 使用 Helm 部署到生产环境
deploy-helm-prod:
	@echo "🚀 使用 Helm 部署到生产环境"
	helm upgrade --install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
		--namespace backup-prod \
		--create-namespace \
		-f deploy/helm/k8s-backup-manager/values.yaml \
		--wait
	@echo "✅ Helm 部署完成"

# 使用 Kustomize 部署
deploy-kustomize:
	@echo "🚀 使用 Kustomize 部署"
	kustomize build deploy/kustomize/base | kubectl apply -f -
	@echo "✅ Kustomize 部署完成"

# 使用 Kustomize 部署到生产环境
deploy-kustomize-prod:
	@echo "🚀 使用 Kustomize 部署到生产环境"
	kustomize build deploy/kustomize/overlays/production | kubectl apply -f -
	@echo "✅ Kustomize 部署完成"

# 运行测试
test:
	@echo "🧪 运行测试"
	python -m pytest tests/test_all.py -v

# 构建并测试镜像
test-image:
	@echo "🧪 构建并测试 Docker 镜像"
	docker build -t $(IMAGE_NAME):test .
	docker run --rm $(IMAGE_NAME):test python src/main.py --help

# 查看镜像大小
image-size:
	@echo "📊 镜像大小:"
	@docker images $(IMAGE) --format "{{.Size}}"

# 清理
clean:
	@echo "🧹 清理构建产物"
	docker rmi $(IMAGE) 2>/dev/null || true
	@echo "✅ 清理完成"

# 进入容器调试
shell:
	@echo "💻 进入容器调试模式"
	docker run --rm -it \
		-v ~/.kube/config:/root/.kube/config:ro \
		-v $$(pwd)/config.yaml:/app/config.yaml:ro \
		$(IMAGE) /bin/bash

.PHONY: docker-compose-up docker-compose-down
# 使用 Docker Compose
docker-compose-up:
	@echo "🐳 启动 Docker Compose 环境"
	docker-compose up -d
	@echo "✅ Docker Compose 启动完成"

docker-compose-down:
	@echo "🐳 停止 Docker Compose 环境"
	docker-compose down
	@echo "✅ Docker Compose 停止完成"
