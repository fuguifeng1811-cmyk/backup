"""
S3 兼容存储处理器
支持 AWS S3、MinIO、Ceph RGW 等 S3 兼容存储
"""

import boto3
import logging
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any


class S3Handler:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, region: str = 'us-east-1'):
        """
        初始化 S3 处理器

        Args:
            endpoint_url: S3 兼容服务端点 URL
            access_key: 访问密钥
            secret_key: 秘密密钥
            region: 区域（默认 us-east-1）
        """
        self.logger = logging.getLogger(__name__)

        # 创建 S3 客户端
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    def upload_file(self, local_file_path: str, bucket: str, remote_key: str) -> bool:
        """
        上传文件到 S3 兼容存储

        Args:
            local_file_path: 本地文件路径
            bucket: 目标桶
            remote_key: 远程键（文件名）

        Returns:
            bool: 上传是否成功
        """
        try:
            self.client.upload_file(local_file_path, bucket, remote_key)
            self.logger.info(f"Successfully uploaded {local_file_path} to {bucket}/{remote_key}")
            return True
        except ClientError as e:
            self.logger.error(f"Failed to upload {local_file_path} to {bucket}/{remote_key}: {e}")
            return False

    def download_file(self, bucket: str, remote_key: str, local_file_path: str) -> bool:
        """
        从 S3 兼容存储下载文件

        Args:
            bucket: 桶名
            remote_key: 远程键
            local_file_path: 本地文件路径

        Returns:
            bool: 下载是否成功
        """
        try:
            self.client.download_file(bucket, remote_key, local_file_path)
            self.logger.info(f"Successfully downloaded {bucket}/{remote_key} to {local_file_path}")
            return True
        except ClientError as e:
            self.logger.error(f"Failed to download {bucket}/{remote_key} to {local_file_path}: {e}")
            return False

    def create_bucket_if_not_exists(self, bucket: str) -> bool:
        """
        如果不存在则创建桶

        Args:
            bucket: 桶名

        Returns:
            bool: 操作是否成功
        """
        try:
            self.client.head_bucket(Bucket=bucket)
            self.logger.info(f"Bucket {bucket} already exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # 桶不存在，创建它
                self.client.create_bucket(Bucket=bucket)
                self.logger.info(f"Created bucket {bucket}")
            else:
                self.logger.error(f"Error checking bucket {bucket}: {e}")
                return False
        return True