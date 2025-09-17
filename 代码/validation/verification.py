from pymongo import MongoClient
from collections import defaultdict

client = MongoClient("mongodb://localhost:27017/")
db = client.github
col_fork = db.repo_with_forks
col_commit = db.commit_nodes1

# 1. 构建 repo_id → father_repo_id 映射
fork_map = {}
for doc in col_fork.find({}, {"repo_id": 1, "father_repo_id": 1}):
    fork_map[doc["repo_id"]] = doc.get("father_repo_id")  # 原始项目 father_repo_id 是 None

# 2. 遍历所有 commit_nodes1 文档，统计每个 repo_id 出现在哪些 DAG 中
from_repo_to_origins = defaultdict(set)

cursor = col_commit.find({}, {"repo": 1, "commits": 1})
for doc in cursor:
    origin_repo = doc["repo"]
    for commit_data in doc["commits"].values():
        for from_repo in commit_data.get("from_repo", []):
            from_repo_to_origins[from_repo].add(origin_repo)

# 3. 找出哪些 fork 出现在多个 repo 的 DAG 中（排除原始项目本身）
conflicts = []
for repo_id, origins in from_repo_to_origins.items():
    if len(origins) > 1:
        true_father = fork_map.get(repo_id)
        if true_father and true_father not in origins:
            conflicts.append({
                "repo_id": repo_id,
                "declared_father": true_father,
                "found_in_dags": list(origins)
            })

# 输出异常仓库
for c in conflicts[:10]:  # 仅显示前 10 项
    print(f"⚠️ Repo: {c['repo_id']} | Declared Father: {c['declared_father']} | Found in DAGs: {c['found_in_dags']}")
print(f"共发现 {len(conflicts)} 个存在多重归属的 fork 仓库")
