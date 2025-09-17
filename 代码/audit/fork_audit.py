#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fork_audit.py v4 - 极速版（去掉 patch-id / 补丁检测）

功能：
- 只比较完全 commit hash，不做 patch-id 等价计算
- 支持多分支 fork vs upstream 审计
- 将结果写入 MongoDB（hashes only）
- 支持 dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import List, Set, Optional

# MongoDB 配置（可通过环境变量覆盖）
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "auditdb")
MONGO_COL = os.environ.get("MONGO_COL", "fork_audits_hashes_only")

def run_git(repo: str, args: List[str], check: bool = True) -> str:
    env = os.environ.copy()
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    env["GIT_PAGER"] = "cat"
    cmd = ["git", "-C", repo] + args
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, env=env)
        return out.decode("utf-8", errors="replace").strip()
    except subprocess.CalledProcessError as e:
        if check:
            sys.stderr.write(f"[git ERROR] {' '.join(cmd)}\n{e.output.decode('utf-8', errors='replace')}\n")
            sys.exit(2)
        return e.output.decode("utf-8", errors="replace").strip()

def is_git_repo(path: str) -> bool:
    try:
        run_git(path, ["rev-parse", "--git-dir"])
        return True
    except SystemExit:
        return False

def list_remote_branches(path: str, remote_name: str) -> List[str]:
    out = run_git(path, ["for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote_name}/"], check=False)
    pref = f"{remote_name}/"
    branches = []
    for line in out.splitlines():
        if line.startswith(pref):
            branches.append(line[len(pref):])
    seen = set()
    ret = []
    for b in branches:
        if b not in seen:
            seen.add(b)
            ret.append(b)
    return ret

def list_local_branches(path: str) -> List[str]:
    out = run_git(path, ["for-each-ref", "--format=%(refname:short)", "refs/heads/"], check=False)
    return [l for l in out.splitlines() if l.strip()]

def iso8601(ts: str) -> str:
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ts

def rev_list(repo: str, ref: str) -> List[str]:
    if not ref:
        return []
    out = run_git(repo, ["rev-list", ref], check=False)
    return [l for l in out.splitlines() if l.strip()]

def union_reachable(repo: str, refs: List[str]) -> Set[str]:
    all_revs: Set[str] = set()
    for r in refs:
        if not r:
            continue
        revs = rev_list(repo, r)
        all_revs.update(revs)
    return all_revs

def upstream_state_at_time(repo: str, upstream_remote: str, branches: List[str], ts: str) -> Set[str]:
    present: Set[str] = set()
    for b in branches:
        tip_t = run_git(repo, ["rev-list", "-n", "1", "--first-parent", f"--before={ts}", f"{upstream_remote}/{b}"], check=False)
        if not tip_t:
            continue
        commits = rev_list(repo, tip_t)
        present.update(commits)
    return present

def fetch_github_created_at(slug: str, token: Optional[str]) -> str:
    import urllib.request, urllib.error, json as _json
    url = f"https://api.github.com/repos/{slug}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            created_at = data.get("created_at")
            if not created_at:
                raise ValueError("created_at missing in API response")
            return created_at
    except Exception as e:
        sys.stderr.write(f"[github ERROR] {slug}: {e}\n")
        raise

def main():
    ap = argparse.ArgumentParser(description="Audit fork vs upstream (hashes only, no patch-id)")
    ap.add_argument("--fork-path", required=True)
    ap.add_argument("--origin-path", required=True)
    ap.add_argument("--fork-name", required=True)
    ap.add_argument("--origin-name", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fork_repo = os.path.abspath(args.fork_path)
    origin_repo = os.path.abspath(args.origin_path)

    if not is_git_repo(fork_repo):
        sys.stderr.write(f"[error] fork-path is not a git repo: {fork_repo}\n")
        sys.exit(2)
    if not is_git_repo(origin_repo):
        sys.stderr.write(f"[error] origin-path is not a git repo: {origin_repo}\n")
        sys.exit(2)

    token = os.environ.get("GH_TOKEN")
    try:
        created_at_raw = fetch_github_created_at(args.fork_name, token)
        ts = iso8601(created_at_raw)
    except Exception:
        ts = "1970-01-01T00:00:00Z"

    # 添加 origin remote
    remotes = run_git(fork_repo, ["remote", "-v"], check=False).splitlines()
    remote_name = None
    for line in remotes:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == origin_repo:
            remote_name = parts[0]
            break
    if not remote_name:
        existing_names = run_git(fork_repo, ["remote"], check=False).splitlines()
        candidate = "tmp_upstream"
        i = 1
        while candidate in existing_names:
            i += 1
            candidate = f"tmp_upstream{i}"
        run_git(fork_repo, ["remote", "add", candidate, origin_repo])
        remote_name = candidate

    # fetch
    run_git(fork_repo, ["fetch", "--all", "--prune"])
    run_git(fork_repo, ["fetch", remote_name, "--prune"])

    # upstream branches
    up_branches = list_remote_branches(fork_repo, remote_name)
    if not up_branches:
        sys.stderr.write(f"[error] No remote branches found on '{remote_name}'\n")
        sys.exit(2)

    # 计算集合
    A_set = upstream_state_at_time(fork_repo, remote_name, up_branches, ts)
    Up_now = union_reachable(fork_repo, [f"{remote_name}/{b}" for b in up_branches])

    fork_local = list_local_branches(fork_repo)
    fork_remotes = run_git(fork_repo, ["remote"], check=False).splitlines()
    fork_refs = [f"refs/heads/{b}" for b in fork_local]
    for r in fork_remotes:
        if r != remote_name:
            bs = list_remote_branches(fork_repo, r)
            fork_refs.extend([f"{r}/{b}" for b in bs])
    Fork_now = union_reachable(fork_repo, fork_refs)

    # A/B/C 集合（hash 完全匹配）
    Up_after = Up_now - A_set
    C_same = Up_after & Fork_now
    B_same = Fork_now - Up_now

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "fork_name": args.fork_name,
        "origin_name": args.origin_name,
        "fork_path": fork_repo,
        "origin_path": origin_repo,
        "fork_created_at": ts,
        "computed_at": now_iso,
        "counts": {
            "A_at_fork": len(A_set),
            "C_same_hash": len(C_same),
            "B_unique_same_hash": len(B_same),
        },
        "hashes": {
            "A_at_fork": list(A_set),
            "C_same_hash": list(C_same),
            "B_unique_same_hash": list(B_same),
        }
    }

    if args.dry_run:
        print(json.dumps({"info": "dry-run", "counts": doc["counts"]}, ensure_ascii=False, indent=2))
        return

    try:
        from pymongo import MongoClient
    except Exception:
        sys.stderr.write("[error] pymongo not installed\n")
        sys.exit(2)

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    col = db[MONGO_COL]

    key = {"fork_name": args.fork_name, "origin_name": args.origin_name, "fork_created_at": ts}
    res = col.update_one(key, {"$set": doc}, upsert=True)

    print(json.dumps({
        "status": "ok",
        "mongo": {"uri": MONGO_URI, "db": MONGO_DB, "col": MONGO_COL},
        "matched_count": getattr(res, "matched_count", None),
        "modified_count": getattr(res, "modified_count", None),
        "upserted_id": str(getattr(res, "upserted_id", "")) if getattr(res, "upserted_id", None) else None,
        "counts": doc["counts"]
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
