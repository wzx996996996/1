import requests
import time
import json
import sys
import os

# ========== 配置 ==========
TOKENS = [t.strip() for t in os.getenv("GITHUB_TOKENS", "").split(",") if t.strip()]
OUTPUT_FILE = "top_star_repos.jsonl"
LANGUAGES = ["C", "C++", "Go"]
PER_PAGE = 100
MAX_REPOS = 1000  # 每种语言最多爬取 1000 个

if not TOKENS:
    print("[warn] 未提供 GITHUB_TOKENS，将匿名访问（速率极低）")

token_idx = 0  # 用于轮换 token

def get_next_token():
    global token_idx
    if not TOKENS:
        return None
    token = TOKENS[token_idx]
    token_idx = (token_idx + 1) % len(TOKENS)
    return token

# ========== 工具函数 ==========
def github_search_repos(language, page=1):
    headers = {"Accept": "application/vnd.github+json"}
    token = get_next_token()
    if token:
        headers["Authorization"] = f"token {token}"
    q = f"language:{language}"
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={PER_PAGE}&page={page}"
    for _ in range(3):  # 最多重试3次
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403:
                print("Hit rate limit, sleeping 60s...")
                time.sleep(60)
            else:
                print(f"Error: {resp.status_code} {resp.text}")
                time.sleep(5)
        except Exception as e:
            print(f"Network error: {e}, retrying...")
            time.sleep(5)
    return None

def save_repos(repos, lang):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for repo in repos:
            repo["_language"] = lang
            f.write(json.dumps(repo, ensure_ascii=False) + "\n")

# ========== 主程序 ==========
def crawl_top_star_repos():
    for lang in LANGUAGES:
        print(f"==== 爬取 {lang} 语言 star 数前 {MAX_REPOS} 的仓库 ====")
        all_repos = []
        for page in range(1, MAX_REPOS // PER_PAGE + 2):
            data = github_search_repos(lang, page)
            if not data or "items" not in data:
                print(f"{lang} page {page} failed or no data.")
                break
            items = data["items"]
            if not items:
                break
            all_repos.extend(items)
            print(f"{lang} page {page}: fetched {len(items)} repos, total so far: {len(all_repos)}")
            if len(all_repos) >= MAX_REPOS:
                break
            time.sleep(1)  # 防止触发速率限制
        # 去重（以 full_name）
        seen = set()
        unique_repos = []
        for repo in all_repos:
            if repo["full_name"] not in seen:
                seen.add(repo["full_name"])
                unique_repos.append(repo)
        save_repos(unique_repos[:MAX_REPOS], lang)
        print(f"{lang} done, saved {len(unique_repos[:MAX_REPOS])} repos.")

if __name__ == "__main__":
    crawl_top_star_repos() 