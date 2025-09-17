import pandas as pd
from pymongo import MongoClient

# 连接到 MongoDB 数据库
client = MongoClient('mongodb://localhost:27017/')
db = client['github']  # 选择数据库
collection = db['pr_commit_data']  # 选择集合（表）

# 读取 CSV 文件
file_path = os.getenv('PR_COMMIT_CSV', os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../1/output/pr_commit_data1.csv')))
df = pd.read_csv(file_path)

# 打印读取的数据，检查是否正确
print(df.head())

# 将数据转换为字典形式，并插入到 MongoDB
records = df.to_dict(orient='records')  # 转换为字典列表

# 批量插入到 MongoDB
collection.insert_many(records)

print(f"Successfully imported {len(records)} records into MongoDB.")
