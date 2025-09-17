import requests
import time
import csv
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# === 配置 ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # 使用环境变量读取 GitHub token
if not GITHUB_TOKEN:
    raise RuntimeError("未设置 GITHUB_TOKEN 环境变量")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
OUTPUT_FILE = os.getenv(
    'PR_COMMIT_OUTPUT',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/output/pr_commit_data1.csv'))
)  # 用于存储分析结果


# 记录已分析的仓库，防止重复分析
def load_processed_data():
    return set()


def save_processed_data(data):
    with open(OUTPUT_FILE, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(["Repo", "PR Number", "Commit SHA", "Author", "Commit Date", "External Repo"])
        for row in data:
            writer.writerow(row)


# 创建一个带重试机制的 requests 会话对象
def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


# 获取仓库的所有 PR
def get_all_prs(owner, repo, session):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all"
    response = session.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Failed to fetch PRs for {owner}/{repo}. Status code: {response.status_code}")
        return []

    return response.json()


# 获取 PR 中的所有 commits
def get_pr_commits(owner, repo, pr_number, session):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    response = session.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Failed to fetch commits for PR {pr_number} in {owner}/{repo}. Status code: {response.status_code}")
        return []

    return response.json()


# 读取 CSV 文件并获取原始仓库信息
def load_repo_data(file_path):
    repo_data = []
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            repo_data.append(row)
    return repo_data


# 主程序
def analyze_repos(file_path):
    session = create_session()  # 创建一个带重试机制的会话对象

    # 读取并获取原始仓库数据
    repo_data = load_repo_data(file_path)
    print(f"Found {len(repo_data)} repositories.")

    # 加载已处理的数据，防止断点续爬时重复分析
    processed_data = load_processed_data()

    all_pr_commit_data = []  # 用于存储所有仓库的 PR 和 commit 信息

    for row in repo_data:
        owner, repo = row['full_name'].split("/")  # 获取仓库的 owner 和 repo
        father_repo_id = row['full_name']  # 原始仓库的 ID

        # 如果该仓库已经处理过，跳过
        if father_repo_id in processed_data:
            print(f"Skipping {father_repo_id}, already processed.")
            continue

        print(f"Analyzing {father_repo_id}...")

        # 获取该原始仓库的所有 PR
        prs = get_all_prs(owner, repo, session)
        print(f"Found {len(prs)} PRs for {owner}/{repo}.")  # 输出找到的 PR 数量

        for pr in prs:
            if isinstance(pr, dict):
                commits = get_pr_commits(owner, repo, pr['number'], session)  # 获取 PR 中的 commits
                print(f"Found {len(commits)} commits for PR {pr['number']}")  # 输出 PR 中提交数
                for commit in commits:
                    # 收集 PR 和 commit 数据
                    external_repo = 'N/A'
                    if pr.get('head') and pr['head'].get('repo'):
                        external_repo = pr['head']['repo'].get('full_name', 'N/A')

                    all_pr_commit_data.append([
                        father_repo_id,  # Repo
                        pr['number'],  # PR Number
                        commit['sha'],  # Commit SHA
                        commit['commit']['author']['name'],  # Author
                        commit['commit']['author']['date'],  # Commit Date
                        external_repo  # External Repo
                    ])
                time.sleep(1)  # 避免请求过于频繁

        # 标记仓库已处理
        processed_data.add(father_repo_id)

    # 将数据保存到 CSV 文件
    save_processed_data(all_pr_commit_data)
    print(f"Finished processing {len(all_pr_commit_data)} records.")


# 运行主程序
if __name__ == "__main__":
    file_path = os.getenv(
        'ORIGINAL_REPOS_CSV',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/output/top100_repos.csv'))
    )  # 指定原始仓库的 CSV 文件路径
    analyze_repos(file_path)  # 执行分析原始仓库的 PR 和 commit 数据
