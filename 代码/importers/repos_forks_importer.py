import csv
import json
from pymongo import MongoClient

# 连接 MongoDB 本地服务器
client = MongoClient("mongodb://localhost:27017/")
db = client["github"]
repos_col = db["repos"]
forks_col = db["forks"]

# 加载 forks 文件为字典：father_id => [forks...]
def load_fork_data(path):
    forks_dict = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            father = item.get("parent_repo")
            if not father:
                continue
            forks_dict.setdefault(father, []).append({
                "repo_id": item["full_name"],
                "html_url": item["html_url"],
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "language": item.get("language"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "father_repo_id": father
            })
    return forks_dict

# 主流程
def import_repos_and_forks(repo_csv, forks_jsonl):
    forks_dict = load_fork_data(forks_jsonl)
    total_repos, total_forks = 0, 0

    with open(repo_csv, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            repo_id = row["full_name"]
            if not repos_col.find_one({"repo_id": repo_id}):
                repo_doc = {
                    "repo_id": repo_id,
                    "name": row.get("name"),
                    "full_name": row.get("full_name"),
                    "html_url": row.get("html_url"),
                    "stars": int(row.get("stars", 0)),
                    "language": row.get("language"),
                    "created_at": row.get("created_at")
                }
                repos_col.insert_one(repo_doc)
                total_repos += 1
                print(f"✅ 插入 repo: {repo_id}")
            else:
                print(f"⚠️  已存在 repo: {repo_id}")

            # 插入对应 forks
            from pymongo import InsertOne

            # 插入对应 forks（一次性查重 + 批量插入）
            forks = forks_dict.get(repo_id, [])
            if forks:
                # 获取 repo_id 列表
                fork_ids = [f["repo_id"] for f in forks]
                # 查询已有的 fork_id
                existing_ids = set(
                    doc["repo_id"] for doc in forks_col.find({"repo_id": {"$in": fork_ids}}, {"repo_id": 1})
                )
                # 构造未存在的插入操作
                operations = [
                    InsertOne(fork) for fork in forks if fork["repo_id"] not in existing_ids
                ]
                if operations:
                    forks_col.bulk_write(operations)
                    print(f"✅ 插入 {len(operations)} 个 forks for {repo_id}")

    print(f"\n🎉 插入完成：{total_repos} 个 repo，{total_forks} 个 forks")

if __name__ == "__main__":
    import_repos_and_forks("top100_repos.csv", "top100_100_forks.jsonl")
