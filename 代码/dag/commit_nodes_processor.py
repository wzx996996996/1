import os
import subprocess
import copy
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
COL_NAME = "commit_nodes1"
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

    print(f"正在读取路径: {repo_path}")  # 输出路径，检查路径是否正确
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


def get_forks_for_repo(repo_id):
    repos_col = db["repo_with_forks"]
    return list(repos_col.find({"father_repo_id": repo_id, "stars": {"$gt": 10}}, {"repo_id": 1}))


def build_and_store_commit_tree(repo_id):
    base_path = os.path.join(BASE_DIR, *repo_id.split("/"))
    print(f"🚀 处理原始仓库: {repo_id}")

    base_dag = load_commit_dag(base_path)
    if base_dag is None:
        print(f"❌ 无法读取仓库 {repo_id}，跳过")
        return

    for node in base_dag.values():
        node["from_repo"] = [repo_id]

    forks = get_forks_for_repo(repo_id)
    print(f"📎 找到 {len(forks)} 个 forks")

    temp_dag = copy.deepcopy(base_dag)
    for fork in forks:
        fork_repo_id = fork["repo_id"]
        fork_path = os.path.join(BASE_DIR, *fork_repo_id.split("/"))
        fork_dag = load_commit_dag(fork_path)
        if fork_dag is None:
            print(f"⚠️ 跳过无法读取的 fork 仓库：{fork_repo_id}")
            continue
        merge_fork_into_base(temp_dag, fork_dag, fork_repo_id)

    commits_chunks = split_dict_by_count(temp_dag, 5000)
    for chunk_key in commits_chunks:
        chunk_data = {
            "repo": repo_id,
            "commits": commits_chunks[chunk_key]
        }
        insert_mongo(col, chunk_data)
    print(f"✅ 仓库 {repo_id} 提交 DAG 插入完成，共分 {len(commits_chunks)} 块\n")


def main():
    repos_col = db["repo_with_forks"]
    origin_repos = list(repos_col.find({"father_repo_id": None}).limit(100))

    print(f"共需处理原始仓库数量: {len(origin_repos)}")
    for repo in origin_repos:
        repo_id = repo["repo_id"]
        build_and_store_commit_tree(repo_id)


if __name__ == "__main__":
    main()
