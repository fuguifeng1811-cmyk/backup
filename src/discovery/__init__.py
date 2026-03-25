"""
应用发现模块 - 识别 K8s 中有状态应用和持久化数据的应用

功能:
- 发现有状态应用（StatefulSet、使用 PVC 的 Deployment/Pod）
- 识别持久化存储（PVC、PV）
- 提取备份相关元数据
"""

import logging
from typing import List, Dict, Optional
from kubernetes import client, config
from kubernetes.client import V1StatefulSet, V1Deployment, V1Pod, V1PersistentVolumeClaim

logger = logging.getLogger(__name__)


class ApplicationDiscovery:
    """应用发现器"""

    def __init__(self, kubeconfig: str = None, context: str = None):
        """
        初始化应用发现器

        Args:
            kubeconfig: kubeconfig 文件路径，None 则使用默认位置
            context: Kubernetes context 名称
        """
        if kubeconfig or context:
            config.load_kube_config(config_file=kubeconfig, context=context)
        else:
            # 尝试 in-cluster 配置（运行在 Pod 中时）
            try:
                config.load_incluster_config()
            except config.ConfigException:
                # 回退到默认 kubeconfig
                config.load_kube_config()

        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()

    def discover_stateful_apps(self, namespaces: List[str] = None) -> List[Dict]:
        """
        发现有状态应用

        Args:
            namespaces: 要扫描的命名空间列表，None 则扫描所有命名空间

        Returns:
            应用列表，每个应用包含元数据和存储信息
        """
        if namespaces is None:
            namespaces = self._get_all_namespaces()

        apps = []

        for ns in namespaces:
            logger.info(f"正在扫描命名空间: {ns}")

            # 发现 StatefulSet
            apps.extend(self._discover_statefulsets(ns))

            # 发现使用 PVC 的 Deployment
            apps.extend(self._discover_pvc_deployments(ns))

            # 发现使用 PVC 的独立 Pod
            apps.extend(self._discover_pvc_pods(ns))

        logger.info(f"共发现 {len(apps)} 个有状态应用")
        return apps

    def _discover_statefulsets(self, namespace: str) -> List[Dict]:
        """发现 StatefulSet"""
        try:
            statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace=namespace)
            results = []

            for sts in statefulsets.items:
                app_info = self._parse_statefulset(sts, namespace)
                if app_info:
                    results.append(app_info)

            return results
        except Exception as e:
            logger.error(f"发现 StatefulSet 失败 (namespace={namespace}): {e}")
            return []

    def _discover_pvc_deployments(self, namespace: str) -> List[Dict]:
        """发现使用 PVC 的 Deployment"""
        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            results = []

            for deploy in deployments.items:
                # 检查是否使用 PVC
                if self._has_pvc(deploy.spec.template.spec):
                    app_info = self._parse_deployment(deploy, namespace)
                    if app_info:
                        results.append(app_info)

            return results
        except Exception as e:
            logger.error(f"发现 Deployment 失败 (namespace={namespace}): {e}")
            return []

    def _discover_pvc_pods(self, namespace: str) -> List[Dict]:
        """发现使用 PVC 的独立 Pod"""
        try:
            pods = self.core_v1.list_namespaced_pod(namespace=namespace)
            results = []

            for pod in pods.items:
                # 检查是否使用 PVC 且不是由控制器管理
                if (self._has_pvc(pod.spec) and
                    not pod.metadata.owner_references):
                    app_info = self._parse_pod(pod, namespace)
                    if app_info:
                        results.append(app_info)

            return results
        except Exception as e:
            logger.error(f"发现 Pod 失败 (namespace={namespace}): {e}")
            return []

    def _parse_statefulset(self, sts: V1StatefulSet, namespace: str) -> Optional[Dict]:
        """解析 StatefulSet 信息"""
        try:
            pvc_templates = []
            if sts.spec.volume_claim_templates:
                for template in sts.spec.volume_claim_templates:
                    pvc_templates.append({
                        'name': template.metadata.name,
                        'storage_class': template.spec.storage_class_name,
                        'size': template.spec.resources.requests.get('storage') if template.spec.resources else None,
                        'access_modes': template.spec.access_modes
                    })

            return {
                'type': 'StatefulSet',
                'name': sts.metadata.name,
                'namespace': namespace,
                'labels': sts.metadata.labels or {},
                'annotations': sts.metadata.annotations or {},
                'replicas': sts.spec.replicas,
                'pvc_templates': pvc_templates,
                'has_pvc': len(pvc_templates) > 0
            }
        except Exception as e:
            logger.error(f"解析 StatefulSet 失败 ({sts.metadata.name}): {e}")
            return None

    def _parse_deployment(self, deploy: V1Deployment, namespace: str) -> Optional[Dict]:
        """解析 Deployment 信息"""
        try:
            pvcs = self._extract_pvcs_from_pod_spec(deploy.spec.template.spec)

            return {
                'type': 'Deployment',
                'name': deploy.metadata.name,
                'namespace': namespace,
                'labels': deploy.metadata.labels or {},
                'annotations': deploy.metadata.annotations or {},
                'replicas': deploy.spec.replicas,
                'pvcs': pvcs,
                'has_pvc': len(pvcs) > 0
            }
        except Exception as e:
            logger.error(f"解析 Deployment 失败 ({deploy.metadata.name}): {e}")
            return None

    def _parse_pod(self, pod: V1Pod, namespace: str) -> Optional[Dict]:
        """解析独立 Pod 信息"""
        try:
            pvcs = self._extract_pvcs_from_pod_spec(pod.spec)

            return {
                'type': 'Pod',
                'name': pod.metadata.name,
                'namespace': namespace,
                'labels': pod.metadata.labels or {},
                'annotations': pod.metadata.annotations or {},
                'pvcs': pvcs,
                'has_pvc': len(pvcs) > 0
            }
        except Exception as e:
            logger.error(f"解析 Pod 失败 ({pod.metadata.name}): {e}")
            return None

    def _has_pvc(self, pod_spec) -> bool:
        """检查 Pod 是否使用 PVC"""
        if not pod_spec or not pod_spec.volumes:
            return False

        for volume in pod_spec.volumes:
            if volume.persistent_volume_claim:
                return True

        return False

    def _extract_pvcs_from_pod_spec(self, pod_spec) -> List[Dict]:
        """从 Pod Spec 中提取 PVC 信息"""
        pvcs = []

        if not pod_spec or not pod_spec.volumes:
            return pvcs

        for volume in pod_spec.volumes:
            if volume.persistent_volume_claim:
                claim_name = volume.persistent_volume_claim.claim_name
                pvcs.append({
                    'name': claim_name,
                    'volume_name': volume.name
                })

        return pvcs

    def _get_all_namespaces(self) -> List[str]:
        """获取所有命名空间"""
        try:
            namespaces = self.core_v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except Exception as e:
            logger.error(f"获取命名空间列表失败: {e}")
            return []

    def get_pvc_details(self, namespace: str, pvc_name: str) -> Optional[Dict]:
        """
        获取 PVC 详细信息

        Args:
            namespace: 命名空间
            pvc_name: PVC 名称

        Returns:
            PVC 详细信息字典
        """
        try:
            pvc = self.core_v1.read_namespaced_persistent_volume_claim(
                name=pvc_name,
                namespace=namespace
            )

            return {
                'name': pvc.metadata.name,
                'namespace': namespace,
                'storage_class': pvc.spec.storage_class_name,
                'size': pvc.spec.resources.requests.get('storage') if pvc.spec.resources else None,
                'access_modes': pvc.spec.access_modes,
                'volume_name': pvc.spec.volume_name,
                'status': pvc.status.phase
            }
        except Exception as e:
            logger.error(f"获取 PVC 详情失败 ({namespace}/{pvc_name}): {e}")
            return None

    def get_pvcs_for_app(self, app: Dict) -> List[Dict]:
        """
        获取应用关联的所有 PVC 详情

        Args:
            app: 应用信息字典

        Returns:
            PVC 详情列表
        """
        namespace = app['namespace']
        pvcs = []

        if app['type'] == 'StatefulSet':
            # StatefulSet 使用 PVC 模板，需要列出所有匹配的 PVC
            try:
                all_pvcs = self.core_v1.list_namespaced_persistent_volume_claim(namespace=namespace)
                for pvc in all_pvcs.items:
                    # 检查 PVC 是否属于该 StatefulSet
                    # StatefulSet 创建的 PVC 命名格式: {volume-claim-name}-{sts-name}-{index}
                    if app['name'] in pvc.metadata.name:
                        pvcs.append(self.get_pvc_details(namespace, pvc.metadata.name))
            except Exception as e:
                logger.error(f"获取 StatefulSet PVC 失败: {e}")

        elif app['type'] in ['Deployment', 'Pod']:
            # Deployment/Pod 直接引用 PVC
            for pvc_info in app.get('pvcs', []):
                pvc_detail = self.get_pvc_details(namespace, pvc_info['name'])
                if pvc_detail:
                    pvcs.append(pvc_detail)

        return pvcs


# 使用示例
if __name__ == "__main__":
    import json

    discovery = ApplicationDiscovery()

    # 发现所有有状态应用
    apps = discovery.discover_stateful_apps()

    # 打印结果
    print(json.dumps(apps, indent=2, ensure_ascii=False))

    # 获取特定应用的 PVC 详情
    if apps:
        first_app = apps[0]
        pvcs = discovery.get_pvcs_for_app(first_app)
        print(f"\n{first_app['name']} 的 PVC 详情:")
        print(json.dumps(pvcs, indent=2, ensure_ascii=False))
