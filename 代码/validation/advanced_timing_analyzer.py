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


# === 核心工具函数 ===
def get_merge_commit_time(repo_path, commit_hash):
    """获取合并提交的时间"""
    try:
        result = subprocess.check_output(
            ["git", "-C", repo_path, "show", "-s", "--format=%ci", commit_hash],
            stderr=subprocess.PIPE,
            timeout=10
        ).decode("utf-8").strip()
        return datetime.strptime(result, "%Y-%m-%d %H:%M:%S %z")
    except Exception as e:
        print(f"获取合并提交时间失败: {commit_hash} 在 {repo_path} 出错: {e}")
        return None


# === 主逻辑 ===
def calculate_merge_time_diffs():
    try:
        # 连接MongoDB并验证
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        col = client[DB_NAME][COLLECTION_NAME]
        print("✅ 成功连接到MongoDB")
    except Exception as e:
        print(f"❌ MongoDB连接失败: {e}")
        return

    # 收集候选提交（有多个来源仓库的提交）
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

    valid_diff_count = 0  # 有时间差的有效合并提交计数器
    total_valid_count = 0  # 总有效合并提交计数器

    for (repo, commit_hash, from_repos) in candidates:
        time_map = {}

        # 获取每个仓库的合并时间
        for from_repo in from_repos:
            try:
                # 构建本地仓库路径
                owner, repo_name = from_repo.split("/", 1)
                local_path = os.path.abspath(
                    os.path.join(LOCAL_REPO_BASE, owner, repo_name)
                )

                # 检查仓库是否存在且为Git仓库
                if not os.path.isdir(local_path) or not os.path.isdir(os.path.join(local_path, ".git")):
                    continue

                # 获取合并提交时间
                merge_time = get_merge_commit_time(local_path, commit_hash)
                if merge_time:
                    time_map[from_repo] = merge_time

            except Exception:
                continue  # 忽略单个仓库的错误

        # 如果有两个及以上仓库的合并时间
        if len(time_map) >= 2:
            total_valid_count += 1
            print(f"\n🔍 正在分析提交 {commit_hash[:8]}...")

            # 输出每个仓库的合并时间
            print("  各仓库合并时间:")
            for repo_name, m_time in time_map.items():
                print(f"    {repo_name}: {m_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # 计算并输出每对仓库的时间差
            repo_names = list(time_map.keys())
            for i in range(len(repo_names)):
                for j in range(i + 1, len(repo_names)):
                    repo1, repo2 = repo_names[i], repo_names[j]
                    time1, time2 = time_map[repo1], time_map[repo2]
                    delta_seconds = abs(time1.timestamp() - time2.timestamp())

                    # 格式化时间差显示
                    if delta_seconds < 60:
                        delta_str = f"{delta_seconds:.2f} 秒"
                    elif delta_seconds < 3600:
                        delta_str = f"{delta_seconds / 60:.2f} 分钟"
                    elif delta_seconds < 86400:
                        delta_str = f"{delta_seconds / 3600:.2f} 小时"
                    else:
                        delta_str = f"{delta_seconds / 86400:.2f} 天"

                    print(f"    {repo1} 和 {repo2} 的合并时间差: {delta_str}")

                # 轻微延迟
                time.sleep(0.1)

    print(f"\n分析完成！")
    print(f"总有效合并提交: {total_valid_count} 个")


if __name__ == "__main__":
    try:
        calculate_merge_time_diffs()
    except KeyboardInterrupt:
        print("\n程序已被用户手动中断")
    except Exception as e:
        print(f"程序运行出错: {str(e)}")

