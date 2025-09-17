#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充 PR commit 修改行数 & 文件级别详情 (断点续跑版，保留原始 _id)
- 从 pr_commit_data 表取 PR/commit
- 调 GitHub API 获取完整 commit stats + files 修改详情
- 保留原有字段 (_id, Repo, PR Number, Commit SHA, Author, Commit Date, External Repo)
- 存入 pr_commit_with_stats 集合
- 支持断点续跑，失败会重试
"""

import csv
import time
import requests
import os
from pymongo import MongoClient
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import SSLError, ConnectionError

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
SRC_COLLECTION = "pr_commit_data"         # 原始 PR 表
DST_COLLECTION = "new_pr_commit_with_stats"   # 新表，带详细修改
CSV_OUTPUT = "pr_commit_with_stats.csv"   # 导出的 CSV 文件
MAX_WORKERS = 10                          # 并发线程数
MAX_RETRIES = 5                           # 最大重试次数
RETRY_DELAY = 5                           # 每次重试延迟秒数

TOKENS = [t.strip() for t in os.getenv("GITHUB_TOKENS", "").split(",") if t.strip()]
if not TOKENS:
    raise RuntimeError("未配置 GITHUB_TOKENS 环境变量（逗号分隔多个 token）")

# ========== 初始化 ==========
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
src = db[SRC_COLLECTION]
dst = db[DST_COLLECTION]
token_cycle = cycle(TOKENS)


def github_get(url):
    """轮换 Token 调 GitHub API，带重试"""
    for attempt in range(MAX_RETRIES):
        for _ in range(len(TOKENS)):
            token = next(token_cycle)
            headers = {"Authorization": f"token {token}"}
            try:
                r = requests.get(url, headers=headers, timeout=30)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 403:  # API 速率限制
                    print("⏳ Token hit rate limit, switching...")
                    time.sleep(2)
                    continue
                else:
                    print(f"❌ Error {r.status_code} for {url}")
                    return None
            except (SSLError, ConnectionError) as e:
                print(f"⚠️ 网络错误: {e}, 重试 {attempt+1}/{MAX_RETRIES}")
                time.sleep(RETRY_DELAY)
                continue
    return None


def process_one(doc):
    """处理单个 PR commit"""
    repo = doc["Repo"]
    sha = doc["Commit SHA"]

    # 已经有数据就跳过 (断点续跑关键点)
    if dst.find_one({"_id": doc["_id"]}):
        return None

    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    data = github_get(url)
    if not data:
        return None

    additions = data.get("stats", {}).get("additions", 0)
    deletions = data.get("stats", {}).get("deletions", 0)

    files_info = []
    for f in data.get("files", []):
        files_info.append({
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
            "patch": f.get("patch"),
        })

    new_doc = {
        "_id": doc["_id"],  # 保留原始 ID
        "Repo": repo,
        "PR Number": doc.get("PR Number"),
        "Commit SHA": sha,
        "Author": doc.get("Author"),
        "Commit Date": doc.get("Commit Date"),
        "External Repo": doc.get("External Repo"),
        "Additions": additions,
        "Deletions": deletions,
        "Files": files_info
    }

    dst.replace_one({"_id": doc["_id"]}, new_doc, upsert=True)
    print(f"✅ {repo}@{sha} +{additions}/-{deletions}, files={len(files_info)}")
    return new_doc


def process_commits():
    docs = list(src.find())
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_doc = {executor.submit(process_one, doc): doc for doc in docs}
        for future in as_completed(future_to_doc):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"❌ Error: {e}")
    return results


def export_csv():
    cursor = dst.find()
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "_id", "Repo", "PR Number", "Commit SHA", "Author", "Commit Date",
            "External Repo", "File", "Status", "Additions", "Deletions", "Changes"
        ])
        for doc in cursor:
            for f in doc.get("Files", []):
                writer.writerow([
                    str(doc.get("_id")),
                    doc.get("Repo"),
                    doc.get("PR Number"),
                    doc.get("Commit SHA"),
                    doc.get("Author"),
                    doc.get("Commit Date"),
                    doc.get("External Repo"),
                    f.get("filename"),
                    f.get("status"),
                    f.get("additions", 0),
                    f.get("deletions", 0),
                    f.get("changes", 0),
                ])
    print(f"📄 CSV 导出完成: {CSV_OUTPUT}")


if __name__ == "__main__":
    process_commits()
    export_csv()
