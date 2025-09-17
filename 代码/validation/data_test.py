from pymongo import MongoClient

# MongoDB 配置
client = MongoClient("mongodb://localhost:27017/")  # MongoDB 地址
db = client.github  # 数据库名
repo_col = db.repo_with_forks  # 原始 fork 仓库信息集合
filtered_repo_col = db.filtered_forks  # 新表：存储 stars >= 10 的 fork 仓库


# 筛选出 stars >= 10 的 fork 仓库
def filter_forks():
    # 查询所有有父仓库的 fork 仓库，并且 stars >= 10
    query = {
        "father_repo_id": {"$ne": None},  # 获取所有有父仓库的 fork 仓库
        "stars": {"$gte": 10}  # 筛选 stars 大于或等于 10 的仓库
    }

    # 获取符合条件的 fork 仓库
    forks_cursor = repo_col.find(query)

    # 获取所有符合条件的仓库
    valid_forks = [fork for fork in forks_cursor]

    # 输出符合条件的 fork 仓库数量
    print(f"Found {len(valid_forks)} fork repos with stars >= 10.")

    return valid_forks


# 将符合条件的 fork 仓库插入到新表中
def insert_filtered_forks():
    # 获取符合条件的 fork 仓库
    valid_forks = filter_forks()

    if valid_forks:
        # 批量插入符合条件的仓库到新表
        filtered_repo_col.insert_many(valid_forks)
        print(f"Inserted {len(valid_forks)} repos into the filtered_forks collection.")
    else:
        print("No repos found with stars >= 10.")


if __name__ == "__main__":
    insert_filtered_forks()  # 执行插入操作
