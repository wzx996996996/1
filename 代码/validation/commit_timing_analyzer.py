import os
import subprocess
from pymongo import MongoClient
from datetime import datetime
import time

# === 配置 ===
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COLLECTION_NAME = "commit_nodes1"
LOCAL_REPO_BASE = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/selected_repos')))
SAMPLE_SIZE = 10000  # 样本数量


def get_merge_commit_time(repo_path, commit_hash):
    """
    获取某个 commit 在该 repo 中的“合并时间”，
    实际上是该 commit 首次出现在该 repo 中的 log 时间。
    """
    try:
        result = subprocess.check_output(
            ["git", "-C", repo_path, "log", commit_hash, "-1", "--pretty=format:%ct"],
            stderr=subprocess.PIPE,
            timeout=10
        ).decode("utf-8").strip()
        if result.isdigit():
            return datetime.fromtimestamp(int(result))
        else:
            return None
    except Exception as e:
        print(f"[!] 获取 merge 时间失败: {commit_hash} 在 {repo_path} 出错: {e}")
        return None



def calculate_merge_time_diffs():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        col = client[DB_NAME][COLLECTION_NAME]
        print("✅ 成功连接到MongoDB")
    except Exception as e:
        print(f"❌ MongoDB连接失败: {e}")
        return

    candidates = []
    try:
        for doc in col.find({f"commits": {"$exists": True}}):
            repo = doc["repo"]
            for commit_hash, commit_obj in doc["commits"].items():
                from_repos = commit_obj.get("from_repo", [])
                if len(from_repos) > 1:
                    candidates.append((repo, commit_hash, from_repos))
            if len(candidates) >= SAMPLE_SIZE:
                break
    except Exception as e:
        print(f"❌ 数据库查询出错: {e}")
        return

    print(f"共找到 {len(candidates)} 个多来源候选提交，开始分析合并时间差...\n")

    diffs = []  # 存放有时间差的提交

    for (repo, commit_hash, from_repos) in candidates:
        time_map = {}

        for from_repo in from_repos:
            try:
                owner, repo_name = from_repo.split("/", 1)
                local_path = os.path.abspath(os.path.join(LOCAL_REPO_BASE, owner, repo_name))

                if not os.path.isdir(local_path) or not os.path.isdir(os.path.join(local_path, ".git")):
                    continue

                merge_time = get_merge_commit_time(local_path, commit_hash)
                if merge_time:
                    time_map[from_repo] = merge_time
            except Exception:
                continue

        if len(time_map) >= 2:
            print(f"\n🔍 Commit {commit_hash[:10]}:")

            for repo_name, tm in time_map.items():
                print(f"    {repo_name}: {tm.strftime('%Y-%m-%d %H:%M:%S')}")

            timestamps = list(time_map.values())
            min_time = min(timestamps)
            max_time = max(timestamps)
            delta = (max_time - min_time).total_seconds()

            if delta > 0:
                # 格式化时间差
                if delta < 60:
                    delta_str = f"{delta:.2f} 秒"
                elif delta < 3600:
                    delta_str = f"{delta / 60:.2f} 分钟"
                elif delta < 86400:
                    delta_str = f"{delta / 3600:.2f} 小时"
                else:
                    delta_str = f"{delta / 86400:.2f} 天"

                print(f"    ⏱ 时间差: {delta_str}")

                diffs.append({
                    "commit": commit_hash,
                    "times": {repo: tm.strftime("%Y-%m-%d %H:%M:%S %z") for repo, tm in time_map.items()},
                    "diff_seconds": delta
                })


    # === 最终输出 ===
    print(f"\n✅ 分析完成，共有 {len(diffs)} 个合并时间存在差异的提交：\n")

    for item in diffs:
        commit = item["commit"]
        times = item["times"]
        delta = item["diff_seconds"]

        # 格式化时间差
        if delta < 60:
            delta_str = f"{delta:.2f} 秒"
        elif delta < 3600:
            delta_str = f"{delta / 60:.2f} 分钟"
        elif delta < 86400:
            delta_str = f"{delta / 3600:.2f} 小时"
        else:
            delta_str = f"{delta / 86400:.2f} 天"

        print(f"🔀 Commit {commit[:10]} 合并时间差: {delta_str}")
        for repo_name, m_time in times.items():
            print(f"    {repo_name}: {m_time}")
        print()

if __name__ == "__main__":
    try:
        calculate_merge_time_diffs()
    except KeyboardInterrupt:
        print("\n程序已被用户手动中断")
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
