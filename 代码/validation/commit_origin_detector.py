import subprocess
import os
from datetime import datetime

def run_git_command(repo_path, args):
    try:
        result = subprocess.check_output(["git", "-C", repo_path] + args, stderr=subprocess.DEVNULL)
        return result.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        return ""

def get_commit_metadata(repo_path, commit_hash):
    output = run_git_command(repo_path, ["show", "--quiet", "--pretty=format:%an|%ae|%ad|%cn|%ce|%cd", commit_hash])
    parts = output.split("|")
    if len(parts) == 6:
        return {
            "Author": parts[0],
            "AuthorEmail": parts[1],
            "AuthorDate": parts[2],
            "Committer": parts[3],
            "CommitterEmail": parts[4],
            "CommitDate": parts[5]
        }
    return {}

def get_branches_tags_containing(repo_path, commit_hash):
    branches = run_git_command(repo_path, ["branch", "--contains", commit_hash])
    tags = run_git_command(repo_path, ["tag", "--contains", commit_hash])
    return {
        "branches": [b.strip() for b in branches.split("\n") if b.strip()],
        "tags": [t.strip() for t in tags.split("\n") if t.strip()]
    }

def get_first_log_time(repo_path, commit_hash):
    log = run_git_command(repo_path, ["log", "--pretty=format:%H|%ct", "--reverse"])
    for line in log.splitlines():
        h, ts = line.split("|")
        if h == commit_hash:
            return datetime.fromtimestamp(int(ts))
    return None

def get_merge_to_main_time(repo_path, commit_hash):
    output = run_git_command(repo_path, [
        "log", "main", "--merges", "--ancestry-path", f"{commit_hash}..main",
        "--pretty=format:%H|%cd|%s"
    ])
    lines = output.splitlines()
    if lines:
        merge_info = lines[0].split("|")
        if len(merge_info) >= 2:
            return merge_info[1]
    return None

def analyze_commit_origin(repo_a_path, repo_b_path, commit_hash):
    data = {}
    for repo_name, path in [("A", repo_a_path), ("B", repo_b_path)]:
        print(f"\n🔍 检查仓库 {repo_name} ...")
        meta = get_commit_metadata(path, commit_hash)
        refs = get_branches_tags_containing(path, commit_hash)
        first_time = get_first_log_time(path, commit_hash)
        merge_time = get_merge_to_main_time(path, commit_hash)

        data[repo_name] = {
            "path": path,
            "author_date": meta.get("AuthorDate"),
            "commit_date": meta.get("CommitDate"),
            "first_seen": first_time,
            "branches": refs["branches"],
            "tags": refs["tags"],
            "merge_to_main": merge_time,
        }

        print(f"✅ Commit 出现在：{first_time}")
        print(f"✅ CommitDate: {meta.get('CommitDate')}")
        print(f"✅ 合并到 main 分支时间: {merge_time}")
        print(f"✅ 所在分支: {refs['branches']}")

    # 简单判断逻辑
    if data["A"]["first_seen"] and data["B"]["first_seen"]:
        if data["A"]["first_seen"] < data["B"]["first_seen"]:
            print("\n🟢 推测源头：Repo A 更早出现该 commit。")
        elif data["A"]["first_seen"] > data["B"]["first_seen"]:
            print("\n🟢 推测源头：Repo B 更早出现该 commit。")
        else:
            print("\n🟡 两者同时出现，可能共享或复制。")
    else:
        print("\n⚠️ 无法在两个 repo 中都找到 commit。")

# 示例使用（请改成你的路径和哈希）
if __name__ == "__main__":
    base = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/selected_repos')))
    repo_a = os.path.join(base, "php/php-src")
    repo_b = os.path.join(base, "EdmondDantes/php-src")
    commit = os.getenv("COMMIT_HASH", "1511172b1b472e817ac42afe2c97b9b713cf5c44")

    analyze_commit_origin(repo_a, repo_b, commit)
