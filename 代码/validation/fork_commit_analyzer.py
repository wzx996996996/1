import requests
import time
import csv
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# === 配置 ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("未设置 GITHUB_TOKEN 环境变量")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
OUTPUT_FILE = os.getenv(
    'PR_COMMIT_JSON',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/output/pr_commit_data.json'))
)


# 记录已分析的仓库和PR，防止重复分析
def load_processed_data():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_processed_data(data):
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=4)


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


# 检查 PR 是否来自外部 fork
def check_if_external_fork(pr, father_repo_id):
    head_repo = pr.get('head')  # 获取 head 信息
    if head_repo and isinstance(head_repo, dict):
        repo_info = head_repo.get('repo')  # 获取 repo 信息
        if repo_info and isinstance(repo_info, dict):
            return repo_info.get('full_name', '') != father_repo_id
    print(f"PR {pr['number']} has an invalid or missing 'head' or 'repo' structure.")
    return False


# 判断 commit 是否来自原始仓库
def is_commit_from_original_repo(commit, father_repo_id):
    author = commit.get('author')
    if author is None:
        return False  # 如果 commit 没有作者信息，返回 False
    return author.get('login', '') == father_repo_id


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

        pr_data = []  # 用于存储当前仓库的所有 PR 和 commit 信息
        for pr in prs:
            if isinstance(pr, dict) and not check_if_external_fork(pr, father_repo_id):  # 如果 PR 来自原始仓库
                commits = get_pr_commits(owner, repo, pr['number'], session)  # 获取 PR 中的 commits
                print(f"Found {len(commits)} commits for PR {pr['number']}")  # 输出 PR 中提交数
                for commit in commits:
                    # 判断 commit 是否来自原始仓库
                    is_from_original_repo = is_commit_from_original_repo(commit, father_repo_id)

                    # 检查 PR 是否包含有效的 'head' 和 'repo'
                    head_repo = pr.get('head')
                    if head_repo and isinstance(head_repo, dict):
                        repo_info = head_repo.get('repo')
                        if repo_info and isinstance(repo_info, dict):
                            pr_data.append({
                                'pr_number': pr['number'],
                                'commit_sha': commit['sha'],
                                'author': commit['commit']['author']['name'],
                                'is_from_original_repo': is_from_original_repo,
                                'external_fork': repo_info.get('full_name', ''),
                                'original_repo': father_repo_id
                            })
                        else:
                            print(f"PR {pr['number']} has missing or invalid 'repo' data in 'head'.")
                    else:
                        print(f"PR {pr['number']} has missing or invalid 'head' data.")

                time.sleep(1)  # 避免请求过于频繁

        # 保存当前仓库的分析结果
        processed_data[father_repo_id] = pr_data
        save_processed_data(processed_data)

        print(f"Finished analyzing {father_repo_id}.")


# 运行主程序
if __name__ == "__main__":
    file_path = os.getenv(
        'ORIGINAL_REPOS_CSV',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../1/output/top100_repos.csv'))
    )
    analyze_repos(file_path)  # 执行分析原始仓库的 PR 和 commit 数据
