import os
import git
import json
from pymongo import MongoClient
from tqdm import tqdm
from git.exc import GitError

# ---------------------- 配置参数 ----------------------
BASE_DIR = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../1/selected_repos")))
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COLLECTION = "repo_with_forks"
FORK_STARS_THRESHOLD = 10
EXAMPLES_COUNT = 5  # 提取的例子数量
OUTPUT_JSON_PATH = "secondary_examples.json"


# ---------------------- 工具函数：获取原始仓库与forks数据 ----------------------
def get_repos_and_forks():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION]

    original_docs = col.find({"forks": {"$exists": True}}, {"repo_id": 1, "forks": 1})
    original_repos = []
    all_forks = []

    for doc in original_docs:
        if "repo_id" in doc and "forks" in doc:
            original_repos.append(doc["repo_id"])
            for fork in doc["forks"]:
                if ("repo_id" in fork and "father_repo_id" in fork and
                        "stars" in fork and fork["stars"] > FORK_STARS_THRESHOLD):
                    all_forks.append((fork["repo_id"], fork["father_repo_id"]))

    return original_repos, all_forks


# ---------------------- 工具函数：获取仓库的commit集合 ----------------------
def get_commit_set(repo_id):
    try:
        owner, repo_name = repo_id.split("/")
    except ValueError:
        return None

    repo_path = os.path.join(BASE_DIR, owner, repo_name)
    if not os.path.exists(repo_path):
        return None

    try:
        repo = git.Repo(repo_path)
        return set(commit.hexsha for commit in repo.iter_commits())
    except (GitError, Exception):
        return None


# ---------------------- 提取二次开发型fork的具体例子 ----------------------
def extract_secondary_dev_examples():
    original_repos, all_forks = get_repos_and_forks()
    if not original_repos or not all_forks:
        print("❌ 未找到有效数据")
        return []

    # 构建原始仓库commit映射
    original_commits = {}
    for repo_id in tqdm(original_repos, desc="加载原始仓库commit"):
        commits = get_commit_set(repo_id)
        if commits is not None:
            original_commits[repo_id] = commits

    # 筛选二次开发型fork并提取例子
    examples = []
    unique_forks = list(set(all_forks))

    for fork_id, father_id in tqdm(unique_forks, desc="查找二次开发例子"):
        if len(examples) >= EXAMPLES_COUNT:
            break  # 达到所需例子数量即停止

        # 检查父仓库数据是否存在
        if father_id not in original_commits:
            continue

        # 获取fork的commit集合
        fork_commits = get_commit_set(fork_id)
        if fork_commits is None:
            continue

        # 计算新commit（fork有而原始仓库没有的）
        new_commits = fork_commits - original_commits[father_id]
        if new_commits:
            # 获取新commit的详细信息（哈希和提交信息）
            new_commits_details = []
            try:
                owner, repo_name = fork_id.split("/")
                repo = git.Repo(os.path.join(BASE_DIR, owner, repo_name))
                for commit_hex in list(new_commits)[:3]:  # 取前3个新commit
                    commit = repo.commit(commit_hex)
                    new_commits_details.append({
                        "commit_hash": commit_hex,
                        "message": commit.message.strip(),
                        "author": commit.author.name,
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M")
                    })
            except Exception:
                new_commits_details = [{"commit_hash": h} for h in list(new_commits)[:3]]

            examples.append({
                "fork_id": fork_id,
                "original_repo_id": father_id,
                "new_commit_count": len(new_commits),
                "sample_new_commits": new_commits_details
            })

    return examples


# ---------------------- 主函数：执行提取并输出结果 ----------------------
def main():
    examples = extract_secondary_dev_examples()

    if not examples:
        print("❌ 未找到符合条件的二次开发型fork例子")
        return

    # 打印示例信息
    print(f"\n✅ 找到{len(examples)}个二次开发型fork例子：")
    for i, example in enumerate(examples, 1):
        print(f"\n例子{i}：")
        print(f"  fork仓库ID：{example['fork_id']}")
        print(f"  原始仓库ID：{example['original_repo_id']}")
        print(f"  新增commit数量：{example['new_commit_count']}")
        print(f"  部分新增commit：")
        for commit in example['sample_new_commits']:
            print(f"    - 哈希：{commit['commit_hash'][:8]}...")
            if "message" in commit:
                print(f"      提交信息：{commit['message'][:50]}...")

    # 保存到JSON
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    print(f"\n📄 详细例子已保存至：{os.path.abspath(OUTPUT_JSON_PATH)}")


if __name__ == "__main__":
    main()
