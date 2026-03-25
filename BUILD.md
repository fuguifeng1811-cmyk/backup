# K8s Backup Manager - 构建和发布说明

## 📦 镜像构建

### 本地构建

```bash
# 构建标准镜像
docker build -t your-registry/k8s-backup-manager:0.1.0 .

# 构建 Alpine 镜像（更小）
docker build -f Dockerfile.alpine -t your-registry/k8s-backup-manager:0.1.0-alpine .

# 构建并测试
make build
make test-image
```

### 多架构构建 (可选)

```bash
# 使用 buildx 构建多架构镜像
docker buildx create --use --name multiarch-builder
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-registry/k8s-backup-manager:0.1.0 \
  --push .
```

### 镜像标签规范

```
latest           - 最新开发版本
0.1.0            - 稳定版本
0.1.0-alpine     - Alpine 版本
sha-<commit>     - Git commit hash
```

## 🚀 发布流程

### 1. 准备发布

```bash
# 更新版本号
VERSION="0.1.0"

# 更新 Chart.yaml
sed -i "s/version: .*/version: $VERSION/" deploy/helm/k8s-backup-manager/Chart.yaml
sed -i "s/appVersion: .*/appVersion: \"$VERSION\"/" deploy/helm/k8s-backup-manager/Chart.yaml

# 提交变更
git add .
git commit -m "chore: prepare release v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"
```

### 2. 构建并推送镜像

```bash
# 构建镜像
docker build -t your-registry/k8s-backup-manager:$VERSION .
docker build -t your-registry/k8s-backup-manager:latest .

# 推送到仓库
docker push your-registry/k8s-backup-manager:$VERSION
docker push your-registry/k8s-backup-manager:latest
```

### 3. 打包 Helm Chart

```bash
# 打包 Chart
cd deploy/helm
helm package k8s-backup-manager

# 生成 index.yaml (如果是 Chart 仓库)
helm repo index . --url https://your-chart-repo.com/charts
```

### 4. 发布到 GitHub (可选)

```bash
# 推送代码和标签
git push origin master
git push origin v$VERSION

# 创建 GitHub Release
gh release create "v$VERSION" \
  --title "Release v$VERSION" \
  --notes "See CHANGELOG.md for details"
```

## 📊 镜像大小对比

| 镜像类型 | 大小 | 说明 |
|---------|------|------|
| 标准镜像 | ~180MB | 基于 Debian |
| Alpine 镜像 | ~120MB | 基于 Alpine，减少 33% |

## 🔒 安全扫描

### 扫描 Docker 镜像

```bash
# 使用 Trivy 扫描
trivy image your-registry/k8s-backup-manager:0.1.0

# 使用 Docker Scout
docker scout quickview your-registry/k8s-backup-manager:0.1.0
```

### 扫描文件系统

```bash
# 扫描项目依赖
trivy fs .

# 扫描 Helm Chart
trivy config deploy/helm/k8s-backup-manager/
```

## 🧪 CI/CD 集成

### GitHub Actions

`.github/workflows/build.yml`:

```yaml
name: Build and Push

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to Registry
        uses: docker/login-action@v2
        with:
          registry: your-registry.com
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Build and Push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            your-registry/k8s-backup-manager:${{ github.ref_name }}
            your-registry/k8s-backup-manager:latest
```

### GitLab CI

`.gitlab-ci.yml`:

```yaml
stages:
  - build
  - test
  - deploy

build-image:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG

test-image:
  stage: test
  script:
    - docker pull $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG
    - docker run $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG python -m pytest tests/

deploy-helm:
  stage: deploy
  script:
    - helm upgrade --install k8s-backup-manager ./deploy/helm/k8s-backup-manager \
        --namespace backup \
        --set image.tag=$CI_COMMIT_TAG
```

## 📋 发布检查清单

### 代码层面

- [ ] 所有测试通过 (`make test`)
- [ ] 代码风格检查通过
- [ ] 更新了 `CHANGELOG.md`
- [ ] 更新了版本号
- [ ] 更新了 `README.md`

### 镜像层面

- [ ] 镜像构建成功
- [ ] 镜像大小合理 (< 200MB)
- [ ] 镜像安全扫描通过
- [ ] 镜像已推送到仓库
- [ ] 镜像标签正确

### Helm Chart 层面

- [ ] Chart 打包成功
- [ ] Chart 验证通过 (`helm lint`)
- [ ] `values.yaml` 示例完整
- [ ] 文档完整

### 文档层面

- [ ] 更新了部署文档 (`DEPLOYMENT.md`)
- [ ] 更新了升级文档 (`UPGRADE.md`)
- [ ] 更新了 CHANGELOG

## 🔄 版本号规范

遵循 [Semantic Versioning](https://semver.org/):

- **MAJOR** (主版本): 不兼容的 API 变更
- **MINOR** (次版本): 向下兼容的功能新增
- **PATCH** (修订号): 向下兼容的问题修正

示例:

```
0.1.0   - 初始版本
0.1.1   - 修复 bug
0.2.0   - 新增功能
1.0.0   - 生产就绪
```

## 📦 发布产物

每次发布应包含:

1. **Docker 镜像**
   - `your-registry/k8s-backup-manager:<version>`
   - `your-registry/k8s-backup-manager:latest`

2. **Helm Chart**
   - `k8s-backup-manager-<version>.tgz`
   - `index.yaml` (如果使用 Chart 仓库)

3. **源代码**
   - Git Tag: `v<version>`
   - GitHub Release

4. **文档**
   - 更新的 `CHANGELOG.md`
   - 更新的文档链接

## 🐳 离线环境发布包

为离线环境准备发布包:

```bash
# 1. 创建发布目录
mkdir -p release-package
cd release-package

# 2. 保存 Docker 镜像
docker save your-registry/k8s-backup-manager:0.1.0 -o k8s-backup-manager.tar

# 3. 打包 Helm Chart
helm package ../deploy/helm/k8s-backup-manager
cp k8s-backup-manager-0.1.0.tgz .

# 4. 复制部署文档
cp ../DEPLOYMENT.md .
cp ../UPGRADE.md .

# 5. 创建安装脚本
cat > install.sh <<'EOF'
#!/bin/bash
# 离线安装脚本

echo "加载 Docker 镜像..."
docker load -i k8s-backup-manager.tar

echo "安装 Helm Chart..."
helm install k8s-backup-manager k8s-backup-manager-0.1.0.tgz \
  --namespace backup \
  --create-namespace

echo "安装完成！"
EOF
chmod +x install.sh

# 6. 打包
tar czf k8s-backup-manager-offline-0.1.0.tar.gz *
```

离线环境安装:

```bash
# 解压
tar xzf k8s-backup-manager-offline-0.1.0.tar.gz

# 运行安装脚本
./install.sh
```
