import os
import subprocess
import copy
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COL_NAME = "commit_nodes"
BASE_DIR = os.getenv("SELECTED_REPOS_BASE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../1/selected_repos")))

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COL_NAME]


def load_commit_dag(repo_path):
    git_cmd = [
        "git", "log",
        "--pretty=format:%H|%P|%s|%ci",
        "--all", "--date=iso"
    ]
    try:
        res = subprocess.run(git_cmd, cwd=repo_path,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             check=True, timeout=3600)
    except Exception as e:
        print(f"❌ 读取提交失败：{repo_path}，错误：{e}")
        return None
    lines = res.stdout.decode("latin-1").splitlines()

    dag = {}
    for line in lines:
        parts = line.strip().split("|", 3)
        if len(parts) != 4:
            continue
        h, parents_str, subject, time_str = parts
        parents = parents_str.split() if parents_str else []
        dag[h] = {
            "hash": h,
            "parents": parents,
            "children": [],
            "subject": subject.encode("latin-1").decode("utf-8", errors="replace"),
            "time": time_str,
            "from_repo": []
        }
    # 建立children关系
    for node in dag.values():
        for p in node["parents"]:
            if p in dag:
                dag[p]["children"].append(node["hash"])
    return dag


def merge_fork_into_base(base_dag, fork_dag, fork_repo_id):
    for h, fork_node in fork_dag.items():
        if h in base_dag:
            if fork_repo_id not in base_dag[h]["from_repo"]:
                base_dag[h]["from_repo"].append(fork_repo_id)
        else:
            new_node = copy.deepcopy(fork_node)
            new_node["from_repo"] = [fork_repo_id]
            base_dag[h] = new_node
            for p in new_node["parents"]:
                if p in base_dag and h not in base_dag[p]["children"]:
                    base_dag[p]["children"].append(h)
            for c in new_node["children"]:
                if c in base_dag and h not in base_dag[c]["parents"]:
                    base_dag[c]["parents"].append(h)


def save_commit_nodes_chunked(dag, batch_size=1000):
    print(f"准备写入数据库，清空旧数据...")
    col.delete_many({})  # 你也可以用条件删除，比如只删当前repo相关的

    nodes = list(dag.values())
    total = len(nodes)
    print(f"准备插入 {total} 条提交节点")

    for i in range(0, total, batch_size):
        batch = nodes[i:i + batch_size]
        col.insert_many(batch)
        print(f"已插入 {min(i + batch_size, total)} / {total} 条提交节点")
    print("所有提交节点写入数据库完成")


def get_forks_for_repo(repo_id):
    repos_col = db["repo_with_forks"]  # 你的fork仓库信息表
    # 只获取fork stars > 10的，可以根据需要调整
    return list(repos_col.find({"father_repo_id": repo_id, "stars": {"$gt": 10}}, {"repo_id": 1}))


# 分割字典为指定大小的块（与示例代码逻辑一致）
def split_dict_by_count(dictionary, chunk_size):
    result = {}
    current_chunk = 1
    count = 0
    for key, value in dictionary.items():
        if count == chunk_size:
            current_chunk += 1
            count = 0
        if current_chunk not in result:
            result[current_chunk] = {}
        result[current_chunk][key] = value
        count += 1
    return result


def insert_mongo(collection, data):
    last_doc = collection.find_one(sort=[('_id', -1)])
    data['_id'] = 1 if not last_doc else last_doc['_id'] + 1
    return collection.insert_one(data).inserted_id


def main():
    repo_id = "php/php-src"  # 这里换成你想处理的原始仓库ID
    base_path = os.path.join(BASE_DIR, *repo_id.split("/"))

    print(f"加载原始仓库 {repo_id} commit DAG...")
    base_dag = load_commit_dag(base_path)
    if base_dag is None:
        print("读取原始仓库失败，退出。")
        return

    # 原始仓库所有commit from_repo初始为自己
    for node in base_dag.values():
        node["from_repo"] = [repo_id]

    forks = get_forks_for_repo(repo_id)
    print(f"找到 {len(forks)} 个fork，开始合并...")

    total_added = 0
    temp_dag = copy.deepcopy(base_dag)
    for fork in forks:
        fork_repo_id = fork["repo_id"]
        fork_path = os.path.join(BASE_DIR, *fork_repo_id.split("/"))
        fork_dag = load_commit_dag(fork_path)
        if fork_dag is None:
            print(f"跳过无法读取fork仓库 {fork_repo_id}")
            continue
        merge_fork_into_base(temp_dag, fork_dag, fork_repo_id)
    print(f"准备写入数据库，清空旧数据...")
    col.delete_many({})  # 你也可以用条件删除，比如只删当前repo相关的
    commits_chunks = split_dict_by_count(temp_dag, 5000)
    for chunk_key in commits_chunks:
        # 构建提交块数据（结构与示例完全一致）
        chunk_data = {
            "repo": repo_id,
            "commits": commits_chunks[chunk_key]
        }
        # 插入到commits_info_new集合
        insert_mongo(col, chunk_data)



if __name__ == "__main__":
    main()
