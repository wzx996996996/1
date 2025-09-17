import csv
from pymongo import MongoClient

# 连接MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client.github
repo_col = db.repo_with_forks

# 清空现有集合（可选，根据需要保留历史数据）
repo_col.delete_many({})
print("已清空repo_with_forks集合现有数据")


def import_original_repos(csv_path):
    """导入原始仓库数据（top100_repos.csv）"""
    original_repos = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            # 解析CSV行（格式：repo_id, html_url, stars, forks, language, created_at, updated_at）
            if len(row) < 7:
                print(f"跳过无效原始仓库行：{row}")
                continue

            repo_id = row[0].strip()
            # 构造原始仓库文档（father_repo_id为null）
            original_repos.append({
                "repo_id": repo_id,
                "html_url": row[1].strip(),
                "stars": int(row[2].strip()) if row[2].strip().isdigit() else 0,
                "forks": int(row[3].strip()) if row[3].strip().isdigit() else 0,
                "language": row[4].strip() if row[4].strip() else None,  # 空语言字段设为None
                "created_at": row[5].strip(),
                "updated_at": row[6].strip(),
                "father_repo_id": None  # 原始仓库无父仓库
            })

    # 批量插入原始仓库
    if original_repos:
        result = repo_col.insert_many(original_repos)
        print(f"成功导入 {len(result.inserted_ids)} 个原始仓库")
    return {repo["repo_id"] for repo in original_repos}  # 返回原始仓库ID集合用于校验


def import_fork_repos(csv_path, valid_original_ids):
    """导入Fork仓库数据（top100_forks.csv），关联原始仓库"""
    fork_repos = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')  # 注意：Fork的CSV是制表符分隔（\t）
        for row in reader:
            # 解析CSV行（字段：parent_repo, full_name, html_url, stargazers_count, ...）
            parent_repo = row["parent_repo"].strip()  # 原始仓库的repo_id
            full_name = row["full_name"].strip()  # Fork仓库的repo_id（格式：user/repo）

            # 校验父仓库是否在原始仓库列表中
            if parent_repo not in valid_original_ids:
                print(f"跳过无效Fork（父仓库不存在）：{full_name} -> {parent_repo}")
                continue

            # 构造Fork仓库文档（father_repo_id关联原始仓库）
            fork_repos.append({
                "repo_id": full_name,
                "html_url": row["html_url"].strip(),
                "stars": int(row["stargazers_count"].strip()) if row["stargazers_count"].strip().isdigit() else 0,
                "forks": int(row["forks_count"].strip()) if row["forks_count"].strip().isdigit() else 0,
                "language": row["language"].strip() if row["language"].strip() else None,
                "created_at": row["created_at"].strip(),
                "updated_at": row["updated_at"].strip(),
                "father_repo_id": parent_repo  # 关联原始仓库的repo_id
            })

    # 批量插入Fork仓库
    if fork_repos:
        result = repo_col.insert_many(fork_repos)
        print(f"成功导入 {len(result.inserted_ids)} 个Fork仓库")


# 执行导入
if __name__ == "__main__":

    original_csv = os.getenv("ORIGINAL_REPOS_CSV", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../1/output/top100_repos.csv")))

    fork_csv = os.getenv("FORKS_CSV", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../1/output/top100_forks.csv")))

    # 1. 导入原始仓库并获取有效ID集合
    valid_original_ids = import_original_repos(original_csv)

    # 2. 导入Fork仓库（关联原始仓库）
    if valid_original_ids:
        import_fork_repos(fork_csv, valid_original_ids)
    else:
        print("未导入任何原始仓库，跳过Fork导入")

    # 验证结果
    print("\n导入结果验证：")
    print(f"原始仓库总数：{repo_col.count_documents({'father_repo_id': None})}")
    print(f"Fork仓库总数：{repo_col.count_documents({'father_repo_id': {'$ne': None}})}")
    print("示例数据：")
    for doc in repo_col.find().limit(3):
        print(f"repo_id: {doc['repo_id']}, father_repo_id: {doc['father_repo_id']}, stars: {doc['stars']}")