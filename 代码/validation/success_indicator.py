from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client.github
col = db.repo_with_forks

# 1. 找所有原始 repo（没有 father_repo_id）
original_repos = list(col.find({"father_repo_id": None}, {"repo_id": 1}))
original_repo_ids = [r["repo_id"] for r in original_repos]

# 记录出现多级 fork 的情况
multi_level_forks = []

for origin_id in original_repo_ids:
    # 找所有直接 fork 自 origin 的 repo
    direct_forks = list(col.find({"father_repo_id": origin_id}, {"repo_id": 1}))
    direct_fork_ids = set([f["repo_id"] for f in direct_forks])

    # 再找它们的子 fork（即间接 fork 自 origin）
    second_level_forks = col.find({"father_repo_id": {"$in": list(direct_fork_ids)}})

    for fork in second_level_forks:
        c_id = fork["repo_id"]
        b_id = fork["father_repo_id"]

        # 再追溯 b 的 father
        b_doc = col.find_one({"repo_id": b_id})
        if not b_doc:
            continue

        a_id = b_doc["father_repo_id"]
        if a_id == origin_id:
            multi_level_forks.append({
                "original_repo": origin_id,
                "b": b_id,
                "c": c_id
            })

print(f"✅ 共发现 {len(multi_level_forks)} 个二级 fork 情况（c <- b <- a）\n")

for entry in multi_level_forks[:10]:  # 最多打印前10个
    print(f"- 原始仓库: {entry['original_repo']}\n  ↳ 一级 fork: {entry['b']}\n    ↳ 二级 fork: {entry['c']}\n")
