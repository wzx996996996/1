import csv
from pymongo import MongoClient
from bson.objectid import ObjectId

REPOS_CSV = "output/top100_repos.csv"
FORKS_CSV = "output/top100_forks.csv"

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "github_top100"
REPO_COLLECTION = "repos"
FORK_COLLECTION = "forks"

def import_to_mongodb():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    repos_col = db[REPO_COLLECTION]
    forks_col = db[FORK_COLLECTION]

    # 清空旧数据（可选）
    repos_col.delete_many({})
    forks_col.delete_many({})

    print("📥 导入 repos ...")
    repo_id_map = {}
    with open(REPOS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {
                "full_name": row["full_name"],
                "html_url": row.get("html_url"),
                "stars": int(row.get("stars", 0)),
                "forks": int(row.get("forks", 0)),
                "language": row.get("language"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at")
            }
            result = repos_col.insert_one(doc)
            repo_id_map[row["full_name"]] = result.inserted_id

    print("📥 导入 forks ...")
    with open(FORKS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            parent = row.get("parent_repo")
            doc = {
                "full_name": row["full_name"],
                "html_url": row.get("html_url"),
                "stargazers_count": int(row.get("stargazers_count", 0)),
                "forks_count": int(row.get("forks_count", 0)),
                "language": row.get("language"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "parent_repo": parent,
                "parent_id": repo_id_map.get(parent)  # 建立引用
            }
            batch.append(doc)
            if len(batch) >= 1000:
                forks_col.insert_many(batch)
                batch = []
        if batch:
            forks_col.insert_many(batch)

    print("✅ 数据已全部导入 MongoDB!")
    print(f"📊 repos 共导入: {repos_col.count_documents({})}")
    print(f"🍴 forks 共导入: {forks_col.count_documents({})}")

if __name__ == "__main__":
    import_to_mongodb()
