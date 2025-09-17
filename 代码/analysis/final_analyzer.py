import os
import csv
from pymongo import MongoClient

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
commits_tree_table = "commit_nodes1"
prs_table = "pr_commit_data"
forks_table = "repo_with_forks"

client = MongoClient(os.getenv('MONGO_URI', MONGO_URI))
db = client[DB_NAME]
commits_tree = db[commits_tree_table]
prs = db[prs_table]
forks = db[forks_table]


# 生成 CSV 表格的函数
def export_to_csv(data, filename=None):
    if filename is None:
        filename = os.getenv('ANALYSIS_CSV', 'analysis_results.csv')
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            "Repo ID", "Forks >= 10", "Contributions >= 10",
            "Contributions < 10", "Developers", "Common Contributions",
            "Forks - Contributions >= 10 - Developers",
            "PR Count", "PR Commits Count", "Stars >= 10 PRs Count", "Stars >= 10 PRs Commits Count"
        ])
        for row in data:
            writer.writerow(row)


# 分析函数
def analyze():
    results = []
    for repo in forks.find():
        contributions_gte_10 = set()
        contributions_lt_10 = set()
        developers = set()
        repo_id = repo['repo_id']
        fork_list = repo['forks']
        fork_set = set()

        # 获取 fork_set (stars >= 10 的仓库)
        for temp in fork_list:
            if temp['stars'] >= 10:
                fork_set.add(temp['repo_id'])

        # 获取开发者贡献的 repo
        for temp in commits_tree.find({'repo': repo_id}):
            for commit in temp['commits']:
                if repo_id not in temp['commits'][commit]['from_repo']:
                    for temp_fork in temp['commits'][commit]['from_repo']:
                        developers.add(temp_fork)

        # 获取贡献数据 (PRs 中的 external repo)
        pr_count = set()
        pr_commits_count = 0
        stars_gte_10_prs_count = set()
        stars_gte_10_prs_commit_count = 0
        for temp in prs.find({'Repo': repo_id}):
            pr_count.add(temp['PR Number'])
            pr_commits_count += 1
            if temp['External Repo'] in fork_set:
                contributions_gte_10.add(temp['External Repo'])
                stars_gte_10_prs_count.add(temp['PR Number'])
                stars_gte_10_prs_commit_count += 1
            else:
                contributions_lt_10.add(temp['External Repo'])

        # 打印或存储分析结果
        common_contributions = len((contributions_gte_10 | contributions_lt_10) & developers)
        fork_diff = len(fork_set - contributions_gte_10 - developers)

        print(f"{repo_id}: {len(fork_set)} forks, {len(contributions_gte_10)} contributions >= 10, "
              f"{len(contributions_lt_10)} contributions < 10, {len(developers)} developers, "
              f"common contributions: {common_contributions}, fork_diff: {fork_diff}")
        print(len(pr_count), pr_commits_count, len(stars_gte_10_prs_count), stars_gte_10_prs_commit_count)

        # 将分析结果添加到列表
        results.append([
            repo_id,
            len(fork_set),
            len(contributions_gte_10),
            len(contributions_lt_10),
            len(developers),
            common_contributions,
            fork_diff,
            len(pr_count),  # PR count
            pr_commits_count,  # PR commits count
            len(stars_gte_10_prs_count),  # Stars >= 10 PRs count
            stars_gte_10_prs_commit_count  # Stars >= 10 PRs commits count
        ])

    # 导出结果到 CSV 文件
    export_to_csv(results)


if __name__ == "__main__":
    analyze()
