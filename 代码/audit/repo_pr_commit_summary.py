#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
按仓库汇总 PR 统计（唯一 PR 数与 PR 提交总数），导出 CSV。

环境变量：
- MONGO_URI        默认 mongodb://localhost:27017/
- MONGO_DB         默认 github
- PR_COLL          默认 pr_commit_data
- PR_SUMMARY_CSV   默认 repo_pr_commit_summary.csv
"""

from __future__ import annotations
import os
import csv
from collections import defaultdict
from pymongo import MongoClient


def main() -> None:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGO_DB", "github")
    pr_coll_name = os.getenv("PR_COLL", "pr_commit_data")
    output_csv = os.getenv("PR_SUMMARY_CSV", "repo_pr_commit_summary.csv")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    pr_coll = db[pr_coll_name]

    # 统计：每个 Repo → {unique_prs, total_commits}
    unique_prs: dict[str, set[int]] = defaultdict(set)
    total_commits: dict[str, int] = defaultdict(int)

    # 只拉需要的字段，降低内存占用
    for doc in pr_coll.find({}, {"Repo": 1, "PR Number": 1}):
        repo = doc.get("Repo")
        prn = doc.get("PR Number")
        if not isinstance(repo, str):
            continue
        try:
            pr_int = int(prn)
        except Exception:
            continue
        unique_prs[repo].add(pr_int)
        total_commits[repo] += 1

    # 导出 CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Repo", "Unique PR Count", "PR Commits Total"])
        for repo in sorted(unique_prs.keys() | total_commits.keys()):
            writer.writerow([repo, len(unique_prs.get(repo, set())), total_commits.get(repo, 0)])

    print(f"✅ Exported summary to {os.path.abspath(output_csv)}")


if __name__ == "__main__":
    main()


