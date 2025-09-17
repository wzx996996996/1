#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充 PR commit 修改行数信息 (多线程版)
- 从 pr_commit_data 表取 PR/commit
- 调 GitHub API 获取增删行数
- 写入 pr_commit_with_stats 集合
- 最后导出 CSV
"""

import csv
import time
import requests
import os
from pymongo import MongoClient
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置 ==========
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "github"
SRC_COLLECTION = "pr_commit_data"         # 原始 PR 表
DST_COLLECTION = "pr_commit_with_stats"   # 新表，带增删行数
CSV_OUTPUT = "pr_commit_with_stats.csv"   # 导出的 CSV 文件
MAX_WORKERS = 10                          # 并发线程数

# 使用环境变量读取 GitHub Tokens（逗号分隔）
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
    """轮换 Token 调 GitHub API"""
    for _ in range(len(TOKENS)):
        token = next(token_cycle)
        headers = {"Authorization": f"token {token}"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 403:  # API 速率限制
            print("⏳ Token hit rate limit, switching...")
            time.sleep(2)
            continue
        else:
            print(f"❌ Error {r.status_code} for {url}")
            return None
    return None


def process_one(doc):
    """处理单个 PR commit"""
    repo = doc["Repo"]
    sha = doc["Commit SHA"]

    # 已经有数据就跳过
    if dst.find_one({"Repo": repo, "Commit SHA": sha}):
        return None

    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    data = github_get(url)
    if not data:
        return None

    additions = data.get("stats", {}).get("additions", 0)
    deletions = data.get("stats", {}).get("deletions", 0)
    files = [f["filename"] for f in data.get("files", [])] if "files" in data else []

    new_doc = {
        "Repo": repo,
        "PR Number": doc.get("PR Number"),
        "Commit SHA": sha,
        "Author": doc.get("Author"),
        "Commit Date": doc.get("Commit Date"),
        "External Repo": doc.get("External Repo"),
        "Additions": additions,
        "Deletions": deletions,
        "Changed Files": files,
    }

    dst.insert_one(new_doc)
    print(f"✅ {repo}@{sha} +{additions}/-{deletions}")
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
            "Repo", "PR Number", "Commit SHA", "Author", "Commit Date",
            "External Repo", "Additions", "Deletions", "Changed Files"
        ])
        for doc in cursor:
            writer.writerow([
                doc.get("Repo"),
                doc.get("PR Number"),
                doc.get("Commit SHA"),
                doc.get("Author"),
                doc.get("Commit Date"),
                doc.get("External Repo"),
                doc.get("Additions", 0),
                doc.get("Deletions", 0),
                ";".join(doc.get("Changed Files", []))
            ])
    print(f"📄 CSV 导出完成: {CSV_OUTPUT}")


if __name__ == "__main__":
    process_commits()
    export_csv()
