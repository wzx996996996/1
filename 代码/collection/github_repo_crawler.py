import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import cycle

# ==== 配置 ====
# 从环境变量读取 GitHub Token，支持逗号分隔多个：GITHUB_TOKENS="tok1,tok2,..."
_TOKENS_ENV = os.getenv("GITHUB_TOKENS", "").strip()
TOKENS = [t.strip() for t in _TOKENS_ENV.split(",") if t.strip()]
if not TOKENS:
    raise RuntimeError("未配置 GITHUB_TOKENS 环境变量，请设置为逗号分隔的 token 列表，例如：export GITHUB_TOKENS=tok1,tok2")
LANGUAGES = ["C", "C++"]
MAX_REPOS = 1000
THREADS = 10
CACHE_DIR = "cache"
OUTPUT_DIR = "cache/output"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

token_cycle = cycle(TOKENS)

def get_headers():
    token = next(token_cycle)
    return {"Authorization": f"token {token}"}

def safe_request(url, params=None):
    for _ in range(len(TOKENS)):
        try:
            res = requests.get(url, headers=get_headers(), params=params)
            if res.status_code == 403:
                print("Rate limited, waiting 3 seconds...")
                time.sleep(3)
                continue
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Request error: {e}, retry after 5 seconds...")
            time.sleep(5)
    print("All tokens exhausted, sleeping 60 seconds...")
    time.sleep(60)
    return safe_request(url, params)

def get_top_repos(lang):
    cache_file = os.path.join(CACHE_DIR, f"top_repos_{lang.replace('+','p')}.json")
    if os.path.exists(cache_file):
        print(f"Using cached top repos for {lang}...")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"Fetching top repos for {lang}...")
    all_repos = []
    pages = MAX_REPOS // 100
    for page in range(1, pages + 1):
        print(f"Fetching page {page} for {lang}...")
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"language:{lang}",
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
            "page": page,
        }
        data = safe_request(url, params)
        if not data or "items" not in data:
            break
        for item in data["items"]:
            all_repos.append({
                "full_name": item["full_name"],
                "html_url": item["html_url"],
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "language": item["language"],
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            })
        time.sleep(1)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(all_repos, f, indent=2, ensure_ascii=False)
    return all_repos

def get_repo_detail(full_name):
    url = f"https://api.github.com/repos/{full_name}"
    data = safe_request(url)
    if data is None:
        print(f"Repo detail not found: {full_name}")
        return {}
    return data

def get_all_forks(full_name):
    forks = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{full_name}/forks"
        data = safe_request(url, params={"per_page": 100, "page": page})
        if not data:
            break
        for fork in data:
            detail = get_repo_detail(fork["full_name"]) or {}
            forks.append({
                "full_name": fork["full_name"],
                "html_url": fork["html_url"],
                "stargazers_count": fork.get("stargazers_count", 0),
                "forks_count": fork.get("forks_count", 0),
                "language": detail.get("language"),
                "created_at": detail.get("created_at"),
                "updated_at": detail.get("updated_at"),
            })
            time.sleep(0.1)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.5)
    return forks

def process_repo(repo):
    print(f"[FORKING] {repo['full_name']}")
    forks = get_all_forks(repo["full_name"])
    print(f"[FORKED] {repo['full_name']} has {len(forks)} forks")
    repo["forks_list"] = forks
    return repo

def crawl_language(lang):
    repos = get_top_repos(lang)
    output_file = os.path.join(OUTPUT_DIR, f"{lang.replace('+','p').lower()}_repos_with_forks.json")

    done_repos = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                done_list = json.load(f)
                done_repos = {r["full_name"] for r in done_list}
            except Exception:
                done_repos = set()

    results = []

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {}
        for repo in repos:
            if repo["full_name"] in done_repos:
                print(f"[SKIP] {repo['full_name']} already done.")
                continue
            futures[executor.submit(process_repo, repo)] = repo["full_name"]

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"[DONE] {result['full_name']} with {len(result['forks_list'])} forks")
            except Exception as e:
                print(f"[ERROR] processing {futures[future]}: {e}")

    # 合并旧数据和新数据
    old_data = []
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                old_data = json.load(f)
            except Exception:
                old_data = []

    combined = old_data + results

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"✅ {lang} data saved to {output_file}")

def main():
    for lang in LANGUAGES:
        crawl_language(lang)

if __name__ == "__main__":
    main()
