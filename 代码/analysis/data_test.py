from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COL_NAME = "commit_nodes1"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COL_NAME]

for node in col.find():
    n = 0
    for commit in node["commits"]:
        if len(node['commits'][commit]['from_repo']) > 1:
            n = n + 1
    print(n)