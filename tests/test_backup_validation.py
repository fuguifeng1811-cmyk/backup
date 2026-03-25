#!/usr/bin/env python3
"""
备份验证功能测试脚本
"""

import os
import tempfile
import shutil
from pathlib import Path
from src.validator.backup_validator import BackupValidator


def create_test_backups():
    """创建测试备份文件"""
    temp_dir = tempfile.mkdtemp()
    backup_files = []

    # 创建测试备份文件
    for i in range(2):
        backup_file = os.path.join(temp_dir, f"test_backup_{i}.sql")
        with open(backup_file, 'w') as f:
            f.write(f"-- Test backup content {i}\nINSERT INTO table_{i} VALUES ({i});\n")
        backup_files.append(backup_file)

    return temp_dir, backup_files


def test_backup_validation():
    """测试备份验证功能"""
    print("开始测试备份验证功能...")

    # 创建测试备份
    temp_dir, backup_files = create_test_backups()
    print(f"创建测试备份文件: {backup_files}")

    # 创建验证器实例
    validator = BackupValidator()

    # 测试校验和计算
    print("\n1. 测试校验和计算...")
    for file_path in backup_files:
        checksum = validator.calculate_checksum(file_path)
        print(f"   {os.path.basename(file_path)}: {checksum[:16]}...")

    # 测试验证元数据创建
    print("\n2. 测试验证元数据创建...")
    metadata_file = validator.create_verification_metadata(backup_files, temp_dir)
    print(f"   验证元数据文件: {metadata_file}")

    # 测试完整性验证
    print("\n3. 测试完整性验证...")
    is_valid, errors = validator.verify_backup_integrity(metadata_file)
    print(f"   完整性验证结果: {'通过' if is_valid else '失败'}")
    if errors:
        print(f"   错误: {errors}")

    # 测试内容验证
    print("\n4. 测试内容验证...")
    for file_path in backup_files:
        content_valid, msg = validator.verify_backup_content(file_path, 'mysql')
        print(f"   {os.path.basename(file_path)}: {'有效' if content_valid else '无效'} - {msg}")

    # 测试修改后的备份验证
    print("\n5. 测试修改后的备份验证...")
    # 修改其中一个备份文件的内容
    with open(backup_files[0], 'w') as f:
        f.write("-- Modified backup content\nINSERT INTO table_0 VALUES (999);\n")

    # 重新验证
    is_valid, errors = validator.verify_backup_integrity(metadata_file)
    print(f"   修改后验证结果: {'通过' if is_valid else '失败'}")
    if errors:
        print(f"   错误: {errors}")

    # 清理测试文件
    shutil.rmtree(temp_dir)
    print(f"\n清理测试目录: {temp_dir}")

    print("\n备份验证功能测试完成!")


if __name__ == "__main__":
    test_backup_validation()