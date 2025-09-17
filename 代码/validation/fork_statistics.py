import datetime
from pymongo import MongoClient
from collections import defaultdict

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

# 4. 生成 markdown 内容
lines = []

today_str = datetime.date.today().isoformat()
lines.append(f"# 📊 Fork 数据统计报告（生成日期：{today_str}）\n")

lines.append(f"## ✅ 已爬取的原始仓库数量：\n共爬取了 **{len(original_repos)} 个原始仓库（repo）**\n")

lines.append("## 🌐 原始仓库 URL 列表（部分示例）\n")
lines.append("| Repo ID | GitHub URL |")
lines.append("|---------|-------------|")
for repo in original_repos[:10]:  # 仅展示前10个
    lines.append(f"| {repo['repo_id']} | {repo['html_url']} |")
lines.append("")

lines.append("## 📊 每个原始仓库的 Fork 数量\n")
lines.append("| Repo ID | Total Forks | Stars ≥10 Forks |")
lines.append("|---------|-------------|------------------|")
for repo in original_repos:
    rid = repo["repo_id"]
    total = fork_stats[rid]["total"]
    stars10 = fork_stats[rid]["stars_10_plus"]
    lines.append(f"| {rid} | {total} | {stars10} |")
lines.append("")

lines.append("## 🧹 筛选说明\n")
lines.append("""
- 只统计 GitHub 上 `fork: true` 的仓库；
- 仅保留具有 `father_repo_id` 字段的 Fork（说明确实从目标 repo fork）；
- 筛选 Stars ≥ 10 的活跃 Fork 参与后续分析；
- 已执行归一处理，避免重复统计（例如多重 fork 与路径聚合）。
""")

lines.append("## 📁 数据导出\n")
lines.append("""
- `repo_family_commit_filtered_simplified.csv`：原始仓库及其活跃 Fork 数据
- `fork_lifespan_all_repos.csv`：各原始仓库下 Fork 的平均存活时间
- `repo_family_commit_filtered_simplified.md`：本 Markdown 统计报告
- 📎 云文档链接：[repo_family_commit_filtered_simplified.md](https://wzx6872056-1369807678.cos.ap-guangzhou.myqcloud.com/repo_family_commit_filtered_simplified.md)
""")

# 5. 保存为 markdown 文件
with open("repo_family_commit_filtered_simplified.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("✅ 报告已保存为 repo_family_commit_filtered_simplified.md")
