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
OUTPUT_JSON_PATH = "pure_contribution.json"  # 输出JSON文件路径


# ---------------------- 步骤1：提取原始仓库及符合条件的forks（stars > 10） ----------------------
def get_original_and_forks():
    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION]

    # 提取所有包含forks数组的原始仓库
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
    print(f"✅ 筛选后（fork stars > {FORK_STARS_THRESHOLD}）的forks总数（含可能缺失的）：{len(all_forks)}个")
    return original_repos, all_forks


# ---------------------- 步骤2：识别Type 1贡献型forks（基础集） ----------------------
def get_type1_forks(original_repos, all_forks):
    type1_forks = [fork_id for fork_id, father_id in all_forks if father_id in original_repos]
    return list(set(type1_forks))  # 去重


# ---------------------- 步骤3：提取原始仓库基准数据 ----------------------
def get_original_baseline(original_repos):
    baseline = {}  # 格式：{repo_id: {"commits": set(), "roots": set()}}

    for repo_id in tqdm(original_repos, desc="提取原始仓库数据"):
        try:
            owner, repo_name = repo_id.split("/")
        except ValueError:
            print(f"⚠️ 跳过格式异常的原始仓库ID：{repo_id}")
            baseline[repo_id] = {"commits": set(), "roots": set()}
            continue

        repo_path = os.path.join(BASE_DIR, owner, repo_name)
        if not os.path.exists(repo_path):
            print(f"⚠️ 跳过不存在的原始仓库路径：{repo_path}")
            baseline[repo_id] = {"commits": set(), "roots": set()}
            continue

        try:
            repo = git.Repo(repo_path)
            commits = set(commit.hexsha for commit in repo.iter_commits())
            roots = set(commit.tree.hexsha for commit in repo.iter_commits())
            baseline[repo_id] = {"commits": commits, "roots": roots}
            print(f"✅ 完成提取：{repo_id}（提交数：{len(commits)}）")
        except GitError as e:
            print(f"⚠️ Git错误（{repo_id}）：{str(e)}")
            baseline[repo_id] = {"commits": set(), "roots": set()}
        except Exception as e:
            print(f"⚠️ 处理错误（{repo_id}）：{str(e)}")
            baseline[repo_id] = {"commits": set(), "roots": set()}

    return baseline


# ---------------------- 步骤4：识别Type 2、Type 3和纯贡献型forks ----------------------
def get_type2_type3_forks(type1_forks, all_forks, original_baseline):
    type2 = []  # 共享提交（Type 2）
    type3 = []  # 共享根目录（Type 3）
    pure_contribution = []  # 纯贡献型forks（仅Type 1）
    skipped_forks = []  # 被跳过的fork（路径不存在或处理失败）
    unique_forks = list(set(all_forks))  # 去重处理

    for fork_id, father_repo_id in tqdm(unique_forks, desc="检测Type 2/3及纯贡献型"):
        # 跳过已分类的fork
        if fork_id in type2 or fork_id in type3 or fork_id in pure_contribution:
            continue

        # 检查父仓库是否在原始仓库基准数据中
        if father_repo_id not in original_baseline:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：父仓库不在原始仓库列表中")
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

        # 提取fork的提交和根目录哈希
        try:
            repo = git.Repo(fork_path)
            fork_commits = set(commit.hexsha for commit in repo.iter_commits())
            fork_roots = set(commit.tree.hexsha for commit in repo.iter_commits())
        except GitError as e:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：Git错误 - {str(e)}")
            continue
        except Exception as e:
            skipped_forks.append(fork_id)
            print(f"⚠️ 跳过fork {fork_id}：处理错误 - {str(e)}")
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
            continue

        # 既不是Type 2也不是Type 3，属于纯贡献型
        pure_contribution.append(fork_id)

    return type2, type3, pure_contribution, skipped_forks


# ---------------------- 主函数：统计并输出JSON结果 ----------------------
def main():
    # 步骤1：获取原始仓库和筛选后的forks（含可能缺失的）
    original_repos, all_forks = get_original_and_forks()
    if not original_repos or not all_forks:
        print("❌ 未找到原始仓库或符合条件的forks，程序终止")
        return

    # 步骤2：获取Type 1基础集（含可能缺失的）
    type1_all = get_type1_forks(original_repos, all_forks)
    print(f"\n📊 Type 1贡献型forks（含可能缺失的）：{len(type1_all)}个")

    # 步骤3：提取原始仓库基准数据
    original_baseline = get_original_baseline(original_repos)

    # 步骤4：检测Type 2/3及纯贡献型forks
    type2, type3, pure_contribution, skipped_forks = get_type2_type3_forks(
        type1_all, all_forks, original_baseline
    )

    # 计算实际有效fork数量（排除被跳过的）
    actually_processed = len(type1_all) - len(skipped_forks)

    # 输出最终统计结果
    print("\n======================================")
    print(f"筛选条件：fork仓库 stars > {FORK_STARS_THRESHOLD}")
    print(f"1. 总forks（含缺失）：{len(type1_all)}个")
    print(f"2. 被跳过的forks（路径不存在/处理失败）：{len(skipped_forks)}个")
    print(f"3. 实际有效统计的forks：{actually_processed}个")
    print("--------------------------------------")
    print(f"实际纯贡献型forks（仅Type 1）：{len(pure_contribution)}个")
    print(f"实际二次开发型forks：")
    print(f"   - Type 2（共享提交）：{len(type2)}个")
    print(f"   - Type 3（共享根目录）：{len(type3)}个")
    print(f"   - 合计：{len(type2) + len(type3)}个")
    print("======================================")

    # 生成JSON输出
    output_data = {
        "description": "Type 1中仅依赖平台标记、无任何代码共享的纯贡献型forks",
        "count": len(pure_contribution),
        "fork_ids": pure_contribution
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 纯贡献型forks的ID已保存至：{os.path.abspath(OUTPUT_JSON_PATH)}")


if __name__ == "__main__":
    main()
