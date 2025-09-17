import csv
from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client.github
col = db.repo_with_forks

# 获取所有原始 repo
original_repos = list(col.find({"fork": False}))
total_original_count = len(original_repos)

# 构建原始 repo 的信息
repo_info_list = []
fork_stats = []

for repo in original_repos:
    repo_id = repo["repo_id"]
    html_url = repo["html_url"]

    # 获取它的所有 fork
    forks = list(col.find({"father_repo_id": repo_id}))
    total_forks = len(forks)
    active_forks = [f for f in forks if f.get("stars", 0) >= 10]
    active_fork_count = len(active_forks)

    repo_info_list.append((repo_id, html_url))
    fork_stats.append((repo_id, total_forks, active_fork_count))

# 生成 CSV 文件
today = datetime.now().strftime("%Y-%m-%d")

# 创建并写入原始仓库 CSV
with open("repo_info_list.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Repo ID", "GitHub URL"])
    for repo_id, html_url in repo_info_list:
        writer.writerow([repo_id, html_url])

# 创建并写入 fork 数据 CSV
with open("fork_stats.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Repo ID", "Total Forks", "Stars ≥10 Forks"])
    for repo_id, total, active in fork_stats:
        writer.writerow([repo_id, total, active])

# 打印提示
print("✅ CSV 文件已生成为 repo_info_list.csv 和 fork_stats.csv")
