import datetime
from pymongo import MongoClient
from collections import defaultdict
import csv

client = MongoClient("mongodb://localhost:27017/")
db = client.github
col = db.repo_with_forks

# 1. 获取原始仓库（father_repo_id 为 null）
original_repos = list(col.find({"father_repo_id": None}))

# 2. 建立 repo_id 到原始仓库的映射
repo_id_url_map = {repo["repo_id"]: repo["html_url"] for repo in original_repos}

# 3. 构造原始 repo -> fork 列表的映射
fork_stats = defaultdict(lambda: {"total": 0, "stars_10_plus": 0})

for fork in col.find({"father_repo_id": {"$ne": None}}):
    father_id = fork["father_repo_id"]
    if father_id in repo_id_url_map:
        fork_stats[father_id]["total"] += 1
        if fork.get("stars", 0) >= 10:
            fork_stats[father_id]["stars_10_plus"] += 1

# 4. 生成 CSV 内容
csv_data = []

# 头部
csv_data.append(["Repo ID", "Total Forks", "Stars ≥10 Forks"])

# 添加数据
for repo in original_repos:
    rid = repo["repo_id"]
    total = fork_stats[rid]["total"]
    stars10 = fork_stats[rid]["stars_10_plus"]
    csv_data.append([rid, total, stars10])

# 5. 保存为 CSV 文件
csv_filename = "repo_family_commit_filtered_simplified.csv"
with open(csv_filename, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(csv_data)

print(f"✅ 报告已保存为 {csv_filename}")
