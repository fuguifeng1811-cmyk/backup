# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Kubernetes Backup Manager tool that automatically discovers stateful applications and generates backup configurations. It identifies StatefulSets, Deployments, and Pods that use PVCs and creates appropriate backup manifests (CronJobs, Jobs, Secrets, etc.).

## Architecture

The application follows a modular design with four main components:

1. **Application Discovery** (`src/discovery/`) - Discovers stateful applications in Kubernetes clusters
2. **Configuration Extraction** (`src/extractor/`) - Extracts backup configurations from annotations/labels
3. **Template Rendering** (`src/renderer/`) - Generates Kubernetes manifests for backups
4. **Main Program** (`src/main.py`) - CLI interface for discover/generate/extract commands

The tool supports multiple application types including MySQL, PostgreSQL, Redis, MinIO, and generic PVC backups via shell scripts in the `scripts/` directory.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp config.example.yaml config.yaml
```

### Running the Application
```bash
# Discover stateful applications
python src/main.py discover

# Discover in specific namespaces
python src/main.py discover --namespace default --namespace production

# Generate backup manifests
python src/main.py generate --output manifests/

# Extract backup configurations
python src/main.py extract
```

### Testing
```bash
# Run tests
python -m pytest tests/test_all.py -v

# Run specific test module
python -m pytest tests/test_discovery.py
```

### Building and Deployment
```bash
# Build Docker image
make build

# Build smaller Alpine image
make build-alpine

# Deploy with Helm
make deploy-helm

# Deploy with Kustomize
make deploy-kustomize

# Test image
make test-image
```

## Key Files and Directories

- `src/main.py` - Main entry point with CLI commands
- `src/discovery/__init__.py` - Application discovery logic
- `src/extractor/__init__.py` - Configuration extraction from annotations
- `src/renderer/__init__.py` - Manifest generation templates
- `scripts/*.sh` - Backup scripts for different application types
- `config.example.yaml` - Configuration file example
- `Makefile` - Build and deployment commands
- `deploy/helm/` - Helm chart for deployment
- `deploy/kustomize/` - Kustomize configurations
- `examples/` - Configuration examples for different databases

## Application Discovery Process

The discovery module identifies three types of stateful applications:
1. StatefulSets with volume claim templates
2. Deployments that use PVCs
3. Standalone Pods that use PVCs

Each discovered application is processed through:
1. Metadata extraction (name, namespace, type, labels)
2. Storage information extraction (PVC details, sizes, storage classes)
3. Annotation-based configuration extraction for backup settings

## Backup Configuration

Applications can be configured for backup using Kubernetes annotations:
- `backup.k8s.io/enabled: "true"` - Enable backup
- `backup.k8s.io/app-type: "mysql"` - Specify application type
- `backup.k8s.io/schedule: "0 2 * * *"` - Backup schedule (cron format)
- `backup.k8s.io/method: "mysqldump"` - Backup method

## Supported Application Types

- MySQL (via mysqldump)
- PostgreSQL (via pg_dump)
- Redis (RDB/AOF)
- MinIO (mc mirror)
- Generic PVC backups (rsync/tar)

The corresponding backup scripts are located in the `scripts/` directory.

## Deployment Options

1. **Helm Chart** (recommended):
   ```bash
   helm install k8s-backup-manager ./deploy/helm/k8s-backup-manager
   ```

2. **Kustomize**:
   ```bash
   kubectl apply -k deploy/kustomize/base
   ```

3. **Direct kubectl**:
   ```bash
   kubectl apply -f manifests/
   ```