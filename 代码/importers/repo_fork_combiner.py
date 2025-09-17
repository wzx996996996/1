from pymongo import MongoClient

# 连接 MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["github"]
repos_col = db["repos"]
forks_col = db["forks"]
combined_col = db["repo_with_forks"]

# 清空已有集合（可选）
combined_col.drop()

# 遍历 repos 表
for repo in repos_col.find():
    repo_id = repo["repo_id"]

    # 找到对应的 forks
    forks = list(forks_col.find({"father_repo_id": repo_id}))

    # 构造合并文档
    combined_doc = {
        **{k: v for k, v in repo.items() if k != "_id"},
        "forks": forks
    }

    # 插入到新集合中
    combined_col.insert_one(combined_doc)
    print(f"✅ 合并完成: {repo_id}，fork 数: {len(forks)}")

print("✅ 所有 repo 合并完毕。")
