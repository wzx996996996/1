import os
import subprocess
from pymongo import MongoClient
from datetime import datetime

# === 配置 ===
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COLLECTION_NAME = "commit_nodes1"
LOCAL_REPO_BASE = "/Applications/Pycharm Project/1/selected_repos"
SAMPLE_SIZE = None  # None 表示全部跑，或设置整数限制数量

def get_commit_time(repo_path, commit_hash):
    try:
        result = subprocess.check_output(
            ["git", "-C", repo_path, "show", "-s", "--format=%cI", commit_hash],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return datetime.fromisoformat(result)
    except Exception:
        return None

def analyze_all():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION_NAME]

    candidates = []

    for doc in col.find({f"commits": {"$exists": True}}):
        repo = doc["repo"]
        for commit_hash, commit_obj in doc["commits"].items():
            from_repos = commit_obj.get("from_repo", [])
            if len(from_repos) > 1:
                candidates.append((repo, commit_hash, from_repos))

    print(f"共找到 {len(candidates)} 个具有多个 from_repo 的 commit，开始分析...\n")

    results = []
    count = 0

    for repo, commit_hash, from_repos in candidates:
        if SAMPLE_SIZE is not None and count >= SAMPLE_SIZE:
            break
        count += 1

        print(f"🔍 Commit: {commit_hash} | 原始仓库: {repo}")
        time_map = {}

        for from_repo in from_repos:
            owner, repo_name = from_repo.split("/", 1)
            local_path = os.path.join(LOCAL_REPO_BASE, owner, repo_name)
            if not os.path.isdir(local_path):
                print(f"  ⚠️ 缺失: {local_path}")
                continue
            t = get_commit_time(local_path, commit_hash)
            if t:
                time_map[from_repo] = t
                print(f"  - {from_repo}: {t.isoformat()}")
            else:
                print(f"  ⚠️ 无法获取时间: {from_repo}")

        if len(time_map) >= 2:
            timestamps = [t.timestamp() for t in time_map.values()]
            delta = max(timestamps) - min(timestamps)
            print(f"⏱️ 时间差（秒）: {delta:.2f}")
            if delta > 0:
                results.append({
                    "commit_hash": commit_hash,
                    "original_repo": repo,
                    "times": {r: t.isoformat() for r, t in time_map.items()},
                    "time_diff_seconds": delta,
                })
        else:
            print("  ⚠️ 有效时间不足 2 个，跳过对比")

        print("-" * 60)

    # 最后统一打印总结
    print(f"\n✅ 共采样 {count} 个 commit，其中时间差不为0的有 {len(results)} 个，详细如下:\n")
    for item in results:
        print(f"🔍 Commit: {item['commit_hash']} | 原始仓库: {item['original_repo']}")
        for r, t in item["times"].items():
            print(f"  - {r}: {t}")
        print(f"⏱️ 时间差（秒）: {item['time_diff_seconds']:.2f}")
        print("-" * 60)

if __name__ == "__main__":
    analyze_all()
