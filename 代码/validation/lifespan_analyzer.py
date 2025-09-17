from pymongo import MongoClient
from datetime import datetime
import csv

client = MongoClient("mongodb://localhost:27017/")
db = client.github
forks_col = db.repo_with_forks  # fork 仓库集合
repos_col = db.repos  # 假设原始仓库集合是 repos


def days_between(d1, d2):
    return (d2 - d1).days


results = []

# 获取所有原始仓库
all_repos = list(repos_col.find({}, {"repo_id": 1}))

for repo in all_repos:
    repo_id = repo.get("repo_id")
    if not repo_id:
        continue

    # 找该原始仓库下 stars>=10 的 fork
    forks = list(forks_col.find({
        "father_repo_id": repo_id,
        "stars": {"$gte": 10}
    }, {"created_at": 1, "updated_at": 1}))

    if forks:
        total_days = 0
        count = 0
        for fork in forks:
            created_str = fork.get("created_at")
            updated_str = fork.get("updated_at")
            if not created_str or not updated_str:
                continue
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                lifespan = days_between(created, updated)
                total_days += lifespan
                count += 1
            except Exception:
                continue
        avg_lifespan = total_days / count if count > 0 else 0
    else:
        avg_lifespan = 0
        count = 0

    results.append({
        "Original Repo ID": repo_id,
        "Average Fork Lifespan (days)": round(avg_lifespan, 2),
        "Fork Count": count
    })

# 按原始仓库ID排序（可选）
results.sort(key=lambda x: x["Original Repo ID"])

# 输出成 CSV (逗号分隔)
with open("fork_lifespan_all_repos.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Original Repo ID", "Average Fork Lifespan (days)", "Fork Count"])
    for r in results:
        writer.writerow([r["Original Repo ID"], r["Average Fork Lifespan (days)"], r["Fork Count"]])
