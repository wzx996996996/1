import os
import git
import json
from pymongo import MongoClient
from tqdm import tqdm
from git.exc import GitError

# ---------------------- 配置参数 ----------------------
BASE_DIR = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../1/selected_repos")))
MONGO_URI = "mongodb://localhost:27017/"  # MongoDB连接地址
DB_NAME = "github"  # 数据库名称
COLLECTION = "repo_with_forks"  # 集合名称
FORK_STARS_THRESHOLD = 10  # 筛选stars > 10的fork仓库
OUTPUT_JSON_PATH = "classification_results.json"  # 输出结果JSON路径


# ---------------------- 步骤1：提取原始仓库及符合条件的forks ----------------------
def get_original_and_forks():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION]

    original_docs = col.find({"forks": {"$exists": True}}, {"repo_id": 1, "forks": 1})
    original_repos = []  # 原始仓库repo_id列表
    all_forks = []  # 存储格式：(fork_repo_id, father_repo_id)

    for doc in original_docs:
        if "repo_id" not in doc or "forks" not in doc:
            continue

        original_repo_id = doc["repo_id"]
        original_repos.append(original_repo_id)

        # 只提取stars > 10的forks
        for fork in doc["forks"]:
            if ("repo_id" in fork and "father_repo_id" in fork and
                    "stars" in fork and fork["stars"] > FORK_STARS_THRESHOLD):
                all_forks.append((fork["repo_id"], fork["father_repo_id"]))

    print(f"✅ 原始仓库数量：{len(original_repos)}个")
    print(f"✅ 筛选后（fork stars > {FORK_STARS_THRESHOLD}）的forks总数：{len(all_forks)}个")
    return original_repos, all_forks


# ---------------------- 步骤2：提取原始仓库的commit集合 ----------------------
def get_original_commits(original_repos):
    original_data = {}  # 格式：{repo_id: 原始仓库的commit集合}

    for repo_id in tqdm(original_repos, desc="提取原始仓库commit"):
        try:
            owner, repo_name = repo_id.split("/")
        except ValueError:
            print(f"⚠️ 跳过格式异常的原始仓库ID：{repo_id}")
            original_data[repo_id] = set()
            continue

        repo_path = os.path.join(BASE_DIR, owner, repo_name)
        if not os.path.exists(repo_path):
            print(f"⚠️ 跳过不存在的原始仓库路径：{repo_path}")
            original_data[repo_id] = set()
            continue

        try:
            repo = git.Repo(repo_path)
            # 获取原始仓库的所有commit哈希
            original_commits = set(commit.hexsha for commit in repo.iter_commits())
            original_data[repo_id] = original_commits
            print(f"✅ 完成提取：{repo_id}（提交数：{len(original_commits)}）")
        except GitError as e:
            print(f"⚠️ Git错误（{repo_id}）：{str(e)}")
            original_data[repo_id] = set()
        except Exception as e:
            print(f"⚠️ 处理错误（{repo_id}）：{str(e)}")
            original_data[repo_id] = set()

    return original_data


# ---------------------- 步骤3：分类forks（贡献型/二次开发型） ----------------------
def classify_forks(all_forks, original_data):
    contribution = []  # 贡献型：无新commit，且保留所有原始commit
    secondary_dev = []  # 二次开发型：有原始仓库没有的新commit
    skipped_forks = []  # 被跳过的fork（路径不存在/处理失败）
    unique_forks = list(set(all_forks))  # 去重处理

    for fork_id, father_repo_id in tqdm(unique_forks, desc="分类forks"):
        # 检查父仓库数据是否存在
        if father_repo_id not in original_data or not original_data[father_repo_id]:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：父仓库数据缺失")
            continue

        # 解析fork路径
        try:
            owner, repo_name = fork_id.split("/")
        except ValueError:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：ID格式异常")
            continue

        fork_path = os.path.join(BASE_DIR, owner, repo_name)
        if not os.path.exists(fork_path):
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：路径不存在")
            continue

        # 提取fork的commit集合
        try:
            repo = git.Repo(fork_path)
            fork_commits = set(commit.hexsha for commit in repo.iter_commits())
        except GitError as e:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：Git错误 - {str(e)}")
            continue
        except Exception as e:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：处理错误 - {str(e)}")
            continue

        # 获取父仓库的原始commit集合
        original_commits = original_data[father_repo_id]

        # 判定逻辑：
        # 1. 二次开发型：fork有原始仓库没有的commit（新commit）
        new_commits = fork_commits - original_commits
        if new_commits:
            secondary_dev.append({
                "fork_id": fork_id,
                "new_commit_count": len(new_commits)
            })
            continue

        # 2. 贡献型：无新commit，且完全包含原始仓库的所有commit
        if fork_commits.issuperset(original_commits):
            contribution.append(fork_id)
        else:
            # 存在既不是贡献型也不是二次开发型的情况（如缺失部分原始commit且无新commit）
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：缺失原始commit且无新commit")

    return contribution, secondary_dev, skipped_forks


# ---------------------- 主函数：执行分类并输出结果 ----------------------
def main():
    # 步骤1：获取原始仓库和forks
    original_repos, all_forks = get_original_and_forks()
    if not original_repos or not all_forks:
        print("❌ 未找到原始仓库或符合条件的forks，程序终止")
        return

    # 步骤2：提取原始仓库的commit数据
    original_data = get_original_commits(original_repos)

    # 步骤3：分类forks
    contribution, secondary_dev, skipped_forks = classify_forks(all_forks, original_data)

    # 统计结果
    total_processed = len(contribution) + len(secondary_dev)
    total_forks = len(set([f[0] for f in all_forks]))

    # 输出统计信息
    print("\n======================================")
    print(f"筛选条件：fork仓库 stars > {FORK_STARS_THRESHOLD}")
    print(f"1. 总forks数量：{total_forks}个")
    print(f"2. 被跳过的forks：{len(skipped_forks)}个")
    print(f"   （原因：路径不存在/格式错误/缺失原始commit且无新commit）")
    print(f"3. 有效统计的forks：{total_processed}个")
    print("--------------------------------------")
    print(f"贡献型forks：{len(contribution)}个")
    print(f"   （特征：无新commit，且保留所有原始commit）")
    print(f"二次开发型forks：{len(secondary_dev)}个")
    print(
        f"   （特征：存在原始仓库没有的新commit，平均每个有{round(sum(d['new_commit_count'] for d in secondary_dev) / len(secondary_dev), 1)}个新commit）")
    print("======================================")

    # 生成JSON结果
    output_data = {
        "total_forks": total_forks,
        "skipped_forks": len(skipped_forks),
        "contribution": {
            "count": len(contribution),
            "description": "无新commit，且保留所有原始commit",
            "fork_ids": contribution
        },
        "secondary_development": {
            "count": len(secondary_dev),
            "description": "存在原始仓库没有的新commit",
            "forks": secondary_dev  # 包含fork_id和新commit数量
        }
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分类结果已保存至：{os.path.abspath(OUTPUT_JSON_PATH)}")


if __name__ == "__main__":
    main()
