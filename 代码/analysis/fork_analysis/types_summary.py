import os
import git
from pymongo import MongoClient
from tqdm import tqdm
from git.exc import GitError

# ---------------------- 配置参数 ----------------------
BASE_DIR = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../1/selected_repos")))
MONGO_URI = "mongodb://localhost:27017/"  # MongoDB连接地址
DB_NAME = "github"  # 数据库名称
COLLECTION = "repo_with_forks"  # 集合名称
FORK_STARS_THRESHOLD = 10  # 筛选stars > 10的fork仓库


# ---------------------- 步骤1：提取原始仓库及符合条件的forks（stars > 10） ----------------------
def get_original_and_forks():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION]

    # 提取所有包含forks数组的原始仓库（不筛选原始仓库的stars）
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
            # 检查fork是否有stars字段且大于阈值
            if ("repo_id" in fork and "father_repo_id" in fork and
                    "stars" in fork and fork["stars"] > FORK_STARS_THRESHOLD):
                all_forks.append((fork["repo_id"], fork["father_repo_id"]))
                print(f"符合条件的fork：{fork['repo_id']}（stars: {fork['stars']}）")

    print(f"\n✅ 原始仓库数量：{len(original_repos)}个")
    print(f"✅ 筛选后（fork stars > {FORK_STARS_THRESHOLD}）的forks总数：{len(all_forks)}个")
    return original_repos, all_forks


# ---------------------- 步骤2：识别Type 1贡献型forks ----------------------
def get_type1_forks(original_repos, all_forks):
    # 筛选父仓库属于原始仓库列表的forks（即Type 1）
    type1_forks = [fork_id for fork_id, father_id in all_forks if father_id in original_repos]
    return list(set(type1_forks))  # 去重


# ---------------------- 步骤3：提取原始仓库基准数据（提交和根目录哈希） ----------------------
def get_original_baseline(original_repos):
    baseline = {}  # 格式：{repo_id: {"commits": set(), "roots": set()}}

    for repo_id in tqdm(original_repos, desc="提取原始仓库数据"):
        try:
            owner, repo_name = repo_id.split("/")
        except ValueError:
            print(f"⚠️ 跳过格式异常的原始仓库ID：{repo_id}（应为'owner/repo'）")
            baseline[repo_id] = {"commits": set(), "roots": set()}
            continue

        repo_path = os.path.join(BASE_DIR, owner, repo_name)
        if not os.path.exists(repo_path):
            print(f"⚠️ 跳过不存在的原始仓库路径：{repo_path}")
            baseline[repo_id] = {"commits": set(), "roots": set()}
            continue

        try:
            repo = git.Repo(repo_path)
            commits = set()  # 提交哈希集合（Type 2依据）
            roots = set()  # 根目录树哈希集合（Type 3依据）

            for commit in repo.iter_commits():
                commits.add(commit.hexsha)
                roots.add(commit.tree.hexsha)

            baseline[repo_id] = {"commits": commits, "roots": roots}
            print(f"✅ 完成提取：{repo_id}（提交数：{len(commits)}）")
        except GitError as e:
            print(f"⚠️ Git错误（{repo_id}）：{str(e)}")
            baseline[repo_id] = {"commits": set(), "roots": set()}
        except Exception as e:
            print(f"⚠️ 处理错误（{repo_id}）：{str(e)}")
            baseline[repo_id] = {"commits": set(), "roots": set()}

    return baseline


# ---------------------- 步骤4：识别Type 2和Type 3二次开发型forks ----------------------
def get_type2_type3_forks(type1_forks, all_forks, original_baseline):
    type2 = []  # 共享提交（Type 2）
    type3 = []  # 共享根目录（Type 3）
    unique_forks = list(set(all_forks))  # 去重处理

    for fork_id, father_repo_id in tqdm(unique_forks, desc="检测Type 2/3"):
        # 跳过已分类的fork
        if fork_id in type2 or fork_id in type3:
            continue

        # 检查父仓库是否在原始仓库基准数据中
        if father_repo_id not in original_baseline:
            print(f"⚠️ 跳过fork {fork_id}：父仓库{father_repo_id}不在原始仓库列表中")
            continue

        # 解析fork路径
        try:
            owner, repo_name = fork_id.split("/")
        except ValueError:
            print(f"⚠️ 跳过格式异常的fork ID：{fork_id}")
            continue

        fork_path = os.path.join(BASE_DIR, owner, repo_name)
        if not os.path.exists(fork_path):
            print(f"⚠️ 跳过不存在的fork路径：{fork_path}")
            continue

        # 提取fork的提交和根目录哈希
        try:
            repo = git.Repo(fork_path)
            fork_commits = set(commit.hexsha for commit in repo.iter_commits())
            fork_roots = set(commit.tree.hexsha for commit in repo.iter_commits())
        except GitError as e:
            print(f"⚠️ Git错误（{fork_id}）：{str(e)}")
            continue
        except Exception as e:
            print(f"⚠️ 处理错误（{fork_id}）：{str(e)}")
            continue

        # 检测Type 2（共享提交）
        orig_commits = original_baseline[father_repo_id]["commits"]
        if fork_commits & orig_commits:
            type2.append(fork_id)
            continue

        # 检测Type 3（共享根目录）
        orig_roots = original_baseline[father_repo_id]["roots"]
        if fork_roots & orig_roots:
            type3.append(fork_id)

    return type2, type3


# ---------------------- 主函数：执行统计流程 ----------------------
def main():
    # 步骤1：获取原始仓库和stars > 10的forks
    original_repos, all_forks = get_original_and_forks()
    if not original_repos or not all_forks:
        print("❌ 未找到原始仓库或符合条件的forks，程序终止")
        return

    # 步骤2：统计Type 1贡献型forks
    type1 = get_type1_forks(original_repos, all_forks)
    contribution_total = len(type1)
    print(f"\n📊 Type 1贡献型forks总数：{contribution_total}个")

    # 步骤3：提取原始仓库基准数据
    original_baseline = get_original_baseline(original_repos)

    # 步骤4：统计Type 2和Type 3二次开发型forks
    type2, type3 = get_type2_type3_forks(type1, all_forks, original_baseline)
    secondary_total = len(type2) + len(type3)
    pure_contribution = contribution_total - secondary_total  # 纯贡献型（非二次开发）

    # 输出最终统计结果
    print("\n======================================")
    print(f"筛选条件：fork仓库 stars > {FORK_STARS_THRESHOLD}")
    print(f"总forks数量：{contribution_total}个")
    print(f"1. 纯贡献型forks（仅Type 1）：{pure_contribution}个")
    print(f"2. 二次开发型forks：")
    print(f"   - Type 2（共享提交）：{len(type2)}个")
    print(f"   - Type 3（共享根目录）：{len(type3)}个")
    print(f"   - 合计：{secondary_total}个")
    print("======================================")


if __name__ == "__main__":
    main()