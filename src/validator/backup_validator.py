"""
备份验证模块
负责验证备份文件的完整性和可用性
"""

import hashlib
import json
import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class BackupValidator:
    """备份验证器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_checksum(self, file_path: str, algorithm: str = 'sha256') -> str:
        """
        计算文件校验和

        Args:
            file_path: 文件路径
            algorithm: 校验算法 (sha256, md5, sha1)

        Returns:
            校验和字符串
        """
        hash_obj = hashlib.new(algorithm)

        with open(file_path, 'rb') as f:
            # 分块读取大文件，避免内存溢出
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def create_verification_metadata(self, backup_files: List[str],
                                   output_dir: str,
                                   algorithm: str = 'sha256') -> str:
        """
        为备份文件创建验证元数据

        Args:
            backup_files: 备份文件列表
            output_dir: 输出目录
            algorithm: 校验算法

        Returns:
            验证元数据文件路径
        """
        verification_data = {
            'verification_info': {
                'created_at': str(os.times().elapsed),
                'algorithm': algorithm,
                'total_files': len(backup_files)
            },
            'files': []
        }

        for file_path in backup_files:
            if os.path.exists(file_path):
                checksum = self.calculate_checksum(file_path, algorithm)
                file_info = {
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'checksum': checksum,
                    'modified_time': os.path.getmtime(file_path)
                }
                verification_data['files'].append(file_info)

        # 保存验证元数据
        metadata_file = os.path.join(output_dir, 'backup_verification.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(verification_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Verification metadata created: {metadata_file}")
        return metadata_file

    def verify_backup_integrity(self, metadata_file: str) -> Tuple[bool, List[str]]:
        """
        验证备份文件完整性

        Args:
            metadata_file: 验证元数据文件路径

        Returns:
            (是否通过验证, 错误列表)
        """
        errors = []

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                verification_data = json.load(f)
        except Exception as e:
            errors.append(f"Cannot read verification metadata: {str(e)}")
            return False, errors

        files = verification_data.get('files', [])
        passed = True

        for file_info in files:
            file_path = file_info['path']

            # 检查文件是否存在
            if not os.path.exists(file_path):
                errors.append(f"File not found: {file_path}")
                passed = False
                continue

            # 检查文件大小
            current_size = os.path.getsize(file_path)
            expected_size = file_info['size']
            if current_size != expected_size:
                errors.append(f"Size mismatch for {file_path}: expected {expected_size}, got {current_size}")
                passed = False
                continue

            # 检查校验和
            current_checksum = self.calculate_checksum(file_path, verification_data['verification_info']['algorithm'])
            expected_checksum = file_info['checksum']
            if current_checksum != expected_checksum:
                errors.append(f"Checksum mismatch for {file_path}: expected {expected_checksum}, got {current_checksum}")
                passed = False
                continue

        if passed:
            self.logger.info("All backup files integrity check passed")
        else:
            self.logger.error(f"Backup integrity check failed: {len(errors)} errors found")

        return passed, errors

    def verify_backup_content(self, backup_file: str, app_type: str) -> Tuple[bool, str]:
        """
        验证备份内容的可用性

        Args:
            backup_file: 备份文件路径
            app_type: 应用类型

        Returns:
            (是否通过验证, 错误信息)
        """
        if not os.path.exists(backup_file):
            return False, f"Backup file does not exist: {backup_file}"

        # 根据应用类型进行内容验证
        if app_type == 'mysql':
            return self._verify_mysql_backup(backup_file)
        elif app_type == 'postgresql':
            return self._verify_postgresql_backup(backup_file)
        elif app_type == 'redis':
            return self._verify_redis_backup(backup_file)
        elif app_type == 'minio':
            return self._verify_minio_backup(backup_file)
        else:
            # 对于通用备份，只做基本的文件检查
            return self._verify_generic_backup(backup_file)

    def _verify_mysql_backup(self, backup_file: str) -> Tuple[bool, str]:
        """验证MySQL备份"""
        try:
            # 检查文件扩展名
            if backup_file.endswith('.sql.gz'):
                # 尝试读取压缩文件的一部分来验证
                import gzip
                with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                    header = f.read(1024)  # 读取前1KB

                    # 检查是否包含mysqldump特征
                    if 'mysqldump' in header.lower() or 'INSERT INTO' in header or 'CREATE TABLE' in header:
                        return True, "Valid MySQL backup"
                    else:
                        return False, "MySQL backup does not contain expected SQL statements"
            elif backup_file.endswith('.sql'):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    header = f.read(1024)

                    if 'mysqldump' in header.lower() or 'INSERT INTO' in header or 'CREATE TABLE' in header:
                        return True, "Valid MySQL backup"
                    else:
                        return False, "MySQL backup does not contain expected SQL statements"
            else:
                return False, f"Unknown MySQL backup format: {backup_file}"
        except Exception as e:
            return False, f"MySQL backup verification failed: {str(e)}"

    def _verify_postgresql_backup(self, backup_file: str) -> Tuple[bool, str]:
        """验证PostgreSQL备份"""
        try:
            if backup_file.endswith('.sql.gz'):
                import gzip
                with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                    header = f.read(1024)

                    # 检查是否包含pg_dump特征
                    if 'PostgreSQL' in header and ('INSERT INTO' in header or 'COPY' in header):
                        return True, "Valid PostgreSQL backup"
                    else:
                        return False, "PostgreSQL backup does not contain expected dump statements"
            elif backup_file.endswith('.sql'):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    header = f.read(1024)

                    if 'PostgreSQL' in header and ('INSERT INTO' in header or 'COPY' in header):
                        return True, "Valid PostgreSQL backup"
                    else:
                        return False, "PostgreSQL backup does not contain expected dump statements"
            elif backup_file.endswith('.dump'):
                # Custom format dump - check magic bytes
                with open(backup_file, 'rb') as f:
                    magic = f.read(5)
                    if magic.startswith(b'PGDMP'):
                        return True, "Valid PostgreSQL custom format backup"
                    else:
                        return False, "Invalid PostgreSQL custom format backup"
            else:
                return False, f"Unknown PostgreSQL backup format: {backup_file}"
        except Exception as e:
            return False, f"PostgreSQL backup verification failed: {str(e)}"

    def _verify_redis_backup(self, backup_file: str) -> Tuple[bool, str]:
        """验证Redis备份"""
        try:
            # Redis备份通常是RDB文件，检查RDB格式头
            with open(backup_file, 'rb') as f:
                header = f.read(9)  # Redis RDB格式头部是9字节

                if header.startswith(b'REDIS'):
                    return True, "Valid Redis RDB backup"
                else:
                    return False, "Invalid Redis RDB format"
        except Exception as e:
            return False, f"Redis backup verification failed: {str(e)}"

    def _verify_minio_backup(self, backup_file: str) -> Tuple[bool, str]:
        """验证MinIO备份"""
        # MinIO备份通常是目录结构，检查其内容
        if os.path.isdir(backup_file):
            # 检查目录是否非空
            if os.listdir(backup_file):
                return True, "Valid MinIO backup directory"
            else:
                return False, "MinIO backup directory is empty"
        else:
            return False, "MinIO backup should be a directory"

    def _verify_generic_backup(self, backup_file: str) -> Tuple[bool, str]:
        """验证通用备份"""
        # 检查文件是否存在且非空
        if os.path.getsize(backup_file) > 0:
            return True, "Valid generic backup"
        else:
            return False, "Generic backup file is empty"


# 使用示例
if __name__ == "__main__":
    validator = BackupValidator()

    # 示例：验证备份文件
    backup_files = [
        "/backup/mysql_backup.sql.gz",
        "/backup/postgres_backup.dump"
    ]

    # 创建验证元数据
    metadata_file = validator.create_verification_metadata(
        backup_files,
        "/backup/",
        algorithm="sha256"
    )

    # 验证备份完整性
    is_valid, errors = validator.verify_backup_integrity(metadata_file)
    print(f"Integrity check: {is_valid}")
    if errors:
        print("Errors:", "\n".join(errors))

    # 验证特定备份内容
    content_valid, msg = validator.verify_backup_content("/backup/mysql_backup.sql.gz", "mysql")
    print(f"MySQL backup content check: {content_valid}, {msg}")