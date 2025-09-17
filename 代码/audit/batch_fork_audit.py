#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_fork_audit.py

- 从 MongoDB 读取原始仓库及其 fork 列表
- 调用 fork_audit.py 对每个 fork 进行审计
- 只处理 stars > 10 的 fork
- 原有 fork_audit.py 功能不修改
"""

import os
import subprocess
import sys
from pymongo import MongoClient

# ---------- 配置 ----------
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "github"
COLLECTION_NAME = "repo_with_forks"

FORK_AUDIT_SCRIPT = os.path.abspath("fork_audit.py")  # 确保 fork_audit.py 在同一目录
LOCAL_REPO_BASE = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/selected_repos')))
# --------------------------

def check_mongodb_connection():
    """检查MongoDB连接"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # 强制连接测试
        print(f"[info] MongoDB连接成功: {MONGO_URI}")
        return True
    except Exception as e:
        print(f"[error] MongoDB连接失败: {e}")
        return False

def check_data_exists():
    """检查数据是否存在"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        col = db[COLLECTION_NAME]
        
        # 检查原始仓库数量
        original_count = col.count_documents({"father_repo_id": None})
        print(f"[info] 找到 {original_count} 个原始仓库")
        
        # 检查fork总数
        total_forks = 0
        for repo in col.find({"father_repo_id": None}):
            total_forks += len(repo.get("forks", []))
        print(f"[info] 总共有 {total_forks} 个fork")
        
        # 检查stars > 10的fork数量
        high_star_forks = 0
        for repo in col.find({"father_repo_id": None}):
            for fork in repo.get("forks", []):
                if fork.get("stars", 0) > 10:
                    high_star_forks += 1
        print(f"[info] 有 {high_star_forks} 个fork的stars > 10")
        
        return original_count > 0
    except Exception as e:
        print(f"[error] 检查数据失败: {e}")
        return False

def run_fork_audit(fork_path, origin_path, fork_name, origin_name):
    """运行fork审计"""
    # 强制使用当前解释器，避免 'python' 不存在
    interpreter = sys.executable
    cmd = [
        interpreter,
        FORK_AUDIT_SCRIPT,
        "--fork-path", fork_path,
        "--origin-path", origin_path,
        "--fork-name", fork_name,
        "--origin-name", origin_name,
        "--detect-patch-equivalents"
    ]

    # 防呆：如果意外变回 "python"，立刻替换回当前解释器
    if cmd[0] == "python":
        cmd[0] = sys.executable

    print(f"[info] 解释器: {interpreter}")
    print(f"[info] 执行命令(list): {cmd}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"[success] fork审计成功: {fork_name}")
        if result.stdout.strip():
            print(f"[stdout]\n{result.stdout}")
        if result.stderr.strip():
            print(f"[stderr]\n{result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[error] fork审计失败: {fork_name}")
        print(f"[error] 返回码: {e.returncode}")
        if e.stdout:
            print(f"[stdout]\n{e.stdout}")
        if e.stderr:
            print(f"[stderr]\n{e.stderr}")
        return False

def check_repo_paths(fork_path, origin_path):
    """检查仓库路径是否存在"""
    if not os.path.exists(fork_path):
        print(f"[warning] fork路径不存在: {fork_path}")
        return False
    if not os.path.exists(origin_path):
        print(f"[warning] origin路径不存在: {origin_path}")
        return False
    return True

def main():
    print("=== 开始批量fork审计 ===")
    
    # 检查MongoDB连接
    if not check_mongodb_connection():
        print("[error] 无法连接到MongoDB，请确保MongoDB正在运行")
        sys.exit(1)
    
    # 检查数据是否存在
    if not check_data_exists():
        print("[error] 数据库中没有找到数据")
        sys.exit(1)
    
    # 检查本地仓库路径
    if not os.path.exists(LOCAL_REPO_BASE):
        print(f"[error] 本地仓库基础路径不存在: {LOCAL_REPO_BASE}")
        sys.exit(1)
    
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    # 查询所有原始仓库（father_repo_id 为 null）
    original_repos = list(col.find({"father_repo_id": None}))
    print(f"\n=== 开始处理 {len(original_repos)} 个原始仓库 ===")

    processed_forks = 0
    successful_forks = 0

    for repo in original_repos:
        origin_name = repo["repo_id"]  # 原始仓库名
        origin_path = os.path.join(LOCAL_REPO_BASE, origin_name)

        forks = repo.get("forks", [])
        print(f"\n--- 处理原始仓库: {origin_name} ({len(forks)} forks) ---")

        for fork in forks:
            fork_name = fork["repo_id"]
            stars = fork.get("stars", 0)
            
            if stars <= 10:
                print(f"[skip] 跳过fork {fork_name} (stars={stars} <= 10)")
                continue

            fork_path = os.path.join(LOCAL_REPO_BASE, fork_name)
            print(f"\n--- 审计fork: {fork_name} (stars={stars}) ---")
            
            # 检查路径
            if not check_repo_paths(fork_path, origin_path):
                continue
            
            processed_forks += 1
            if run_fork_audit(fork_path, origin_path, fork_name, origin_name):
                successful_forks += 1

    print(f"\n=== 审计完成 ===")
    print(f"处理了 {processed_forks} 个fork")
    print(f"成功 {successful_forks} 个")
    print(f"失败 {processed_forks - successful_forks} 个")

if __name__ == "__main__":
    main()
