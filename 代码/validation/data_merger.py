import os
import subprocess
from pymongo import MongoClient
from datetime import datetime
import time

# === 配置 ===
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COLLECTION_NAME = "commit_nodes1"
LOCAL_REPO_BASE = "/Applications/Pycharm Project/1/selected_repos"
SAMPLE_SIZE = 10000  # 小规模测试数量


# === 工具函数 ===
def get_merge_commit_time(repo_path, merge_commit_hash):
    """获取合并提交(merge commit)的时间，使用%ci格式"""
    try:
        # 使用%ci格式获取合并提交时间
        result = subprocess.check_output(
            ["git", "-C", repo_path, "show", "-s", "--format=%ci", merge_commit_hash],
            stderr=subprocess.DEVNULL,
            timeout=10  # 增加超时设置，避免命令挂起
        ).decode("utf-8").strip()

        # 解析%ci格式的时间字符串 (YYYY-MM-DD HH:MM:SS +0000)
        return datetime.strptime(result, "%Y-%m-%d %H:%M:%S %z")
    except subprocess.TimeoutExpired:
        # 仅在调试时显示，正常运行时静默
        # print(f"⏰ 超时: {merge_commit_hash} in {repo_path}")
        return None
    except Exception as e:
        # 仅在调试时显示，正常运行时静默
        # print(f"❌ 获取失败: {merge_commit_hash} in {repo_path} -> {e}")
        return None


# === 主逻辑 ===
def check_merge_time_differences():
    try:
        # 连接MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # 验证连接
        client.admin.command('ping')
        col = client[DB_NAME][COLLECTION_NAME]
        print("✅ 成功连接到MongoDB")
    except Exception as e:
        print(f"❌ MongoDB连接失败: {e}")
        return

    # 收集有多个来源仓库的提交
    candidates = []
    try:
        for doc in col.find({f"commits": {"$exists": True}}):
            repo = doc["repo"]
            for commit_hash, commit_obj in doc["commits"].items():
                from_repos = commit_obj.get("from_repo", [])
                if len(from_repos) > 1:
                    candidates.append((repo, commit_hash, from_repos))

            # 达到样本数量则停止
            if len(candidates) >= SAMPLE_SIZE:
                break
    except Exception as e:
        print(f"❌ 数据库查询出错: {e}")
        return

    print(f"共找到 {len(candidates)} 个具有多个来源仓库的合并提交，开始分析...\n")

    # 分析每个候选提交的时间差
    valid_count = 0  # 记录有效分析的数量
    for idx, (repo, commit_hash, from_repos) in enumerate(candidates, 1):
        time_map = {}

        for from_repo in from_repos:
            try:
                owner, repo_name = from_repo.split("/", 1)
                local_path = os.path.join(LOCAL_REPO_BASE, owner, repo_name)

                if not os.path.isdir(local_path):
                    continue  # 本地仓库不存在，直接跳过

                # 获取合并提交时间
                commit_time = get_merge_commit_time(local_path, commit_hash)
                if commit_time:
                    time_map[from_repo] = commit_time
            except Exception:
                continue  # 处理出错，直接跳过

        # 只处理有效时间记录足够的情况
        if len(time_map) >= 2:
            valid_count += 1
            print(f"🔍 分析 {valid_count}/{len(candidates)}: 合并提交 {commit_hash} (原始仓库: {repo})")
            print("  时间记录:")
            for repo_name, t in time_map.items():
                print(f"    {repo_name}: {t.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # 计算时间差
            timestamps = [t.timestamp() for t in time_map.values()]
            min_ts, max_ts = min(timestamps), max(timestamps)
            delta_seconds = max_ts - min_ts

            # 转换为更易读的格式
            if delta_seconds < 60:
                delta_str = f"{delta_seconds:.2f} 秒"
            elif delta_seconds < 3600:
                delta_str = f"{delta_seconds / 60:.2f} 分钟"
            elif delta_seconds < 86400:
                delta_str = f"{delta_seconds / 3600:.2f} 小时"
            else:
                delta_str = f"{delta_seconds / 86400:.2f} 天"

            print(f"  ⏱️ 最大时间差: {delta_str}")
            print("-" * 80)
            # 稍微延迟一下，避免请求过于频繁
            time.sleep(0.1)

    print(f"\n分析完成，共找到 {valid_count} 个有效合并提交时间差记录")


if __name__ == "__main__":
    try:
        check_merge_time_differences()
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
    except Exception as e:
        print(f"程序发生未预期错误: {e}")
