#!/usr/bin/env python3
"""
Git per-file commit DAGs → MongoDB (function API, no CLI, no DOT files).

This module builds, for each file in a Git repository, a **reduced commit DAG** that only
contains commits which touched that file. Non-file commits are "hidden" while preserving
reachability (nearest in-set ancestors), so you get a concise, per-file commit-tree.

It then persists a hierarchical model into MongoDB using a single collection (default `nodes`):
- Root node: `type="repo"` (the repo itself)
- Directory nodes: `type="dir"` (nested under repo/dir)
- File nodes: `type="file"` (nested under a dir) with embedded `commits[]` and `edges[]`.

Public functions
----------------
- prepare_repo_graph(repo_path, follow_renames=False, since=None, include_globs=None) -> dict
    Compute all structures in-memory (no DB I/O) and return a dict payload.

- persist_repo_to_mongo(repo_path, mongo_uri, db="git_graph", coll="nodes",
                        clear_first=False, follow_renames=False, since=None,
                        include_globs=None) -> str
    Build + persist everything into MongoDB; returns `repo_id`.

Dependencies
------------
- Git (CLI) available on PATH
- pymongo: `pip install pymongo`
"""

from __future__ import annotations
import datetime as dt
import hashlib
import re
import shlex
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, TypedDict

MONGO_URI = os.getenv("GIT_GRAPH_MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("GIT_GRAPH_MONGO_DB", "Fork_Technical_Lag")
MONGO_COLL = os.getenv("GIT_GRAPH_MONGO_COLL", "test")
CLEAR_FIRST = os.getenv("GIT_GRAPH_CLEAR_FIRST", "false").lower() == "true"
FOLLOW_RENAMES_DEFAULT = os.getenv("GIT_GRAPH_FOLLOW_RENAMES", "true").lower() == "true"
SINCE_DEFAULT = os.getenv("GIT_GRAPH_SINCE")  # e.g., "2023-01-01" or None
INCLUDE_GLOBS_DEFAULT = [s for s in os.getenv("GIT_GRAPH_INCLUDE", "").split(",") if s] or None

# Base directory where your checked-out repos live, e.g. 1/selected_repos
# You can override this via env var SELECTED_REPOS_BASE
SELECTED_REPOS_BASE = Path(
    os.getenv(
        "SELECTED_REPOS_BASE",
        str(Path(__file__).resolve().parents[3] / "1" / "selected_repos"),
    )
).resolve()

# -----------------------------
# C/C++ code file filter (non-intrusive)
# -----------------------------
# Only keep C/C++ source headers by default during file traversal; other types are skipped.
# This does NOT remove or change any existing logic, it only filters which paths enter the mapping.
_CODE_FILE_EXTS = {".c", ".h", ".cpp", ".cc", ".hpp", ".cxx"}

def _is_code_file(path_str: str) -> bool:
    try:
        return Path(path_str).suffix.lower() in _CODE_FILE_EXTS
    except Exception:
        return False


class RepoGraphData(TypedDict):
    repo: Path
    parents: Dict[str, List[str]]
    meta: Dict[str, Tuple[int, str, str]]
    file_commits: Dict[str, Set[str]]
    groups: Dict[str, Set[str]]
    rep_commits: Dict[str, Set[str]]
    rep_display: Dict[str, str]


# =========================
# Git helpers
# =========================

def run_git(repo: Path, args: List[str]) -> str:
    """Run a git command in the given repo and return stdout as text."""
    cmd = ["git"] + args
    try:
        out = subprocess.check_output(cmd, cwd=str(repo), stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        msg_cmd = " ".join(shlex.quote(a) for a in cmd)
        msg_out = e.output.decode("utf-8", errors="replace")
        # 注意：这里必须是单行字符串，\n 用转义，不要回车断开！
        raise RuntimeError(f"Git failed: {msg_cmd}\n{msg_out}")


def load_commit_parents(repo: Path) -> Dict[str, List[str]]:
    """Return mapping commit -> list of parent SHAs (topo-ordered)."""
    text = run_git(repo, ["rev-list", "--topo-order", "--all", "--parents"])
    parents: Dict[str, List[str]] = {}
    for line in text.splitlines():
        if not line:
            continue
        toks = line.split()
        parents[toks[0]] = toks[1:]
    return parents


def load_commit_meta(repo: Path) -> Dict[str, Tuple[int, str, str]]:
    """
    Return mapping commit -> (unix_ts, author, subject).

    ts = %ct (committer timestamp, seconds since epoch, UTC)
    author = %an (author name)
    subject = %s  (first line of commit message)
    """
    fmt = "%H%x01%ct%x01%an%x01%s"
    # 用 log 而不是 show，确保遍历到 --all 的完整提交集合
    text = run_git(repo, ["log", "--all", f"--pretty=format:{fmt}"])
    meta: Dict[str, Tuple[int, str, str]] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("\x01")
        if len(parts) != 4:
            continue
        sha, ts, author, subj = parts
        try:
            meta[sha] = (int(ts), author, subj)
        except ValueError:
            # 极少数异常行，忽略
            continue
    return meta



# =========================
# Rename-union structure
# =========================

class DSU:
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}
        self.display: Dict[str, str] = {}

    def _add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            self.display[x] = x

    def find(self, x: str) -> str:
        self._add(x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str, prefer: Optional[str] = None) -> str:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            if prefer is not None:
                self.display[ra] = prefer
            return ra
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        if prefer is not None:
            self.display[ra] = prefer
        return ra


# =========================
# File ↔ commits mapping
# =========================

RE_STATUS = re.compile(
    r'^(?P<code>[A-Z][0-9]{0,3})\t(?P<a>[^\t]+)(?:\t(?P<b>.+))?$'
)

# -----------------------------
# C/C++ source file filter
# -----------------------------
ALLOWED_CODE_EXTS = {".c", ".h", ".cpp", ".cc", ".hpp", ".cxx"}

def is_code_file(path: Optional[str]) -> bool:
    if not path:
        return False
    p = path.lower()
    # quick ignore for renames that produce devnull-like paths
    if p in {"/dev/null", "dev/null"}:
        return False
    _, ext = os.path.splitext(p)
    return ext in ALLOWED_CODE_EXTS

def load_file_commits(
        repo: Path,
        follow_renames: bool = False,
        since: Optional[str] = None,
        include_globs: Optional[List[str]] = None,
) -> Tuple[Dict[str, Set[str]], DSU]:
    """Parse `git log --all --name-status` once to build mapping: path -> {commit SHAs}."""
    args = ["log", "--all", "-M", "-C", "--name-status", "--pretty=format:COMMIT%x01%H"]
    if since:
        args.insert(1, f"--since={since}")
    text = run_git(repo, args)

    file_commits: Dict[str, Set[str]] = defaultdict(set)
    dsu = DSU()

    cur: Optional[str] = None
    for raw in text.splitlines():
        if not raw:
            continue
        if raw.startswith("COMMIT\x01"):
            cur = raw.split("\x01", 1)[1]
            continue
        if cur is None:
            continue
        m = RE_STATUS.match(raw)
        if not m:
            continue
        code = m.group("code")
        a = m.group("a").replace("\\", "/")
        b = m.group("b")
        if b is not None:
            b = b.replace("\\", "/")

        kind = code[0]
        if kind in {"M", "A", "D"}:
            if is_code_file(a):
                file_commits[a].add(cur)
        elif kind == "R":  # rename
            if b is None:
                continue
            if is_code_file(a):
                file_commits[a].add(cur)
            if is_code_file(b):
                file_commits[b].add(cur)
            if follow_renames and is_code_file(a) and is_code_file(b):
                dsu.union(a, b, prefer=b)
        elif kind == "C":  # copy (not unified)
            if b is None:
                continue
            if is_code_file(b):
                file_commits[b].add(cur)
        else:
            if is_code_file(a):
                file_commits[a].add(cur)

    if include_globs:
        kept: Dict[str, Set[str]] = {}
        for path, cs in file_commits.items():
            if any(Path(path).match(glob) for glob in include_globs):
                kept[path] = cs
        file_commits = kept

    return file_commits, dsu


# =========================
# Per-file induced graphs
# =========================

def nearest_s_ancestors_factory(parents: Dict[str, List[str]], sset: Set[str]):
    """Return a function nearest(x) yielding the nearest ancestors of x that lie in sset."""
    cache: Dict[str, Set[str]] = {}

    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))

    def nearest(x: str) -> Set[str]:
        if x in cache:
            return cache[x]
        if x in sset:
            cache[x] = {x}
            return cache[x]
        res: Set[str] = set()
        for p in parents.get(x, []):
            res.update(nearest(p))
        cache[x] = res
        return res

    return nearest


def build_per_file_edges(parents: Dict[str, List[str]], sset: Set[str]) -> Set[Tuple[str, str]]:
    """Compute edges (u -> v) within the reduced per-file graph for commit set sset."""
    edges: Set[Tuple[str, str]] = set()
    nearest = nearest_s_ancestors_factory(parents, sset)
    for c in sset:
        for p in parents.get(c, []):
            for a in nearest(p):
                if a != c:
                    edges.add((a, c))
    return edges


# =========================
# MongoDB persistence
# =========================

def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def compute_repo_id(repo: Path) -> str:
    """Return a stable repo_id.

    If the repo is inside the SELECTED_REPOS_BASE and its path looks like
    .../selected_repos/<owner>/<name>, then return "<owner>/<name>".
    Otherwise fall back to a hash of the absolute path.
    """
    abs_repo = repo.resolve()
    try:
        rel = abs_repo.relative_to(SELECTED_REPOS_BASE)
        parts = [p for p in rel.parts if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except Exception:
        pass
    return sha1_hex(str(abs_repo))


def mongo_connect(uri: str, db_name: str, coll_name: str):
    try:
        from pymongo import MongoClient, ASCENDING
    except Exception as e:
        raise ImportError("pymongo is required: pip install pymongo") from e
    client = MongoClient(uri)
    db = client[db_name]
    coll = db[coll_name]
    coll.create_index([("repo_id", ASCENDING), ("type", ASCENDING), ("path", ASCENDING)], unique=True,
                      name="repo_type_path")
    coll.create_index([("repo_id", ASCENDING), ("parent_id", ASCENDING)], name="repo_parent")
    coll.create_index([("repo_id", ASCENDING), ("type", ASCENDING)], name="repo_type")
    return coll


def node_id(repo_id: str, ntype: str, path: str) -> str:
    """Deterministic _id for idempotent upserts."""
    key = f"{repo_id}|{ntype}|{path}"
    return sha1_hex(key)


def all_dir_prefixes(path: str) -> List[str]:
    parts = [p for p in path.split("/") if p]
    res: List[str] = []
    for i in range(1, len(parts)):
        res.append("/".join(parts[:i]))
    return res


def mongo_persist_hierarchy(
        coll,
        repo: Path,
        rep_display: Dict[str, str],
        groups: Dict[str, Set[str]],
        rep_commits: Dict[str, Set[str]],
        parents: Dict[str, List[str]],
        meta: Dict[str, Tuple[int, str, str]],
        clear_first: bool = False,
) -> str:
    """Persist repo → dir → file hierarchy with per-file commit-tree into MongoDB.

    Returns the `repo_id`.
    """
    from pymongo import UpdateOne

    repo_id = compute_repo_id(repo)

    if clear_first:
        coll.delete_many({"repo_id": repo_id})

    # Root repo node
    root_id = node_id(repo_id, "repo", "")
    root_doc = {
        "_id": root_id,
        "type": "repo",
        "repo_id": repo_id,
        "name": repo.name,
        "abs_path": str(repo.resolve()),
    }

    ops: List[UpdateOne] = [
        UpdateOne({"_id": root_id}, {"$setOnInsert": root_doc}, upsert=True)
    ]

    # Directory nodes (ensure parents first by depth)
    dir_set: Set[str] = set()
    for display_path in rep_display.values():
        for d in all_dir_prefixes(display_path):
            dir_set.add(d)
    dir_list = sorted(dir_set, key=lambda p: p.count("/"))

    for dpath in dir_list:
        parent_path = dpath.rsplit("/", 1)[0] if "/" in dpath else ""
        parent_id = root_id if parent_path == "" else node_id(repo_id, "dir", parent_path)
        did = node_id(repo_id, "dir", dpath)
        ops.append(UpdateOne(
            {"_id": did},
            {"$setOnInsert": {
                "_id": did, "type": "dir", "repo_id": repo_id,
                "path": dpath, "name": dpath.split("/")[-1], "parent_id": parent_id,
            }},
            upsert=True,
        ))

    # File nodes with embedded commit-tree
    for rep, display_path in rep_display.items():
        parent_path = display_path.rsplit("/", 1)[0] if "/" in display_path else ""
        parent_id = root_id if parent_path == "" else node_id(repo_id, "dir", parent_path)
        fid = node_id(repo_id, "file", display_path)

        sset = rep_commits[rep]
        edges = sorted(build_per_file_edges(parents, sset))
        commits_list = sorted(
            (
                {"sha": h, "ts": meta.get(h, (0, "", ""))[0],
                 "author": meta.get(h, (0, "", ""))[1],
                 "subject": meta.get(h, (0, "", ""))[2]}
                for h in sset
            ),
            key=lambda d: (d["ts"], d["sha"]),
        )
        edges_list = [{"src": u, "dst": v} for (u, v) in edges]

        ops.append(UpdateOne(
            {"_id": fid},
            {"$set": {
                "type": "file", "repo_id": repo_id, "path": display_path,
                "name": display_path.split("/")[-1], "parent_id": parent_id,
                "aliases": sorted(list(groups[rep])),
                "logical_key": rep,
                "commits": commits_list,
                "edges": edges_list,
            }},
            upsert=True,
        ))

    if ops:
        res = coll.bulk_write(ops, ordered=False)
        # Optionally return counts if needed: res.upserted_count, res.modified_count

    return repo_id


# =========================
# Public API
# =========================

def prepare_repo_graph(
        repo_path: str | Path,
        *,
        follow_renames: bool = False,
        since: Optional[str] = None,
        include_globs: Optional[List[str]] = None,
) -> RepoGraphData:
    """Build in-memory structures for the repo without persisting anywhere.

    Returns a dict with keys: `repo`, `parents`, `meta`, `file_commits`, `groups`,
    `rep_commits`, `rep_display`.
    """
    repo = Path(repo_path)
    if not (repo / ".git").exists():
        raise ValueError(f"Not a Git repo: {repo}")

    parents = load_commit_parents(repo)
    meta = load_commit_meta(repo)
    file_commits, dsu = load_file_commits(repo, follow_renames=follow_renames, since=since, include_globs=include_globs)

    groups: Dict[str, Set[str]] = defaultdict(set)
    for pth in file_commits:
        rep = dsu.find(pth) if follow_renames else pth
        groups[rep].add(pth)

    rep_commits: Dict[str, Set[str]] = {}
    rep_display: Dict[str, str] = {}
    for rep, paths in groups.items():
        s: Set[str] = set()
        for p in paths:
            s.update(file_commits[p])
        rep_commits[rep] = s
        disp = getattr(dsu, "display", {}).get(rep, None)
        # Prefer the path with most touches as display fallback
        if not disp:
            disp = sorted(paths, key=lambda x: (-(len(file_commits[x])), x))[0]
        rep_display[rep] = disp

    return {
        "repo": repo,
        "parents": parents,
        "meta": meta,
        "file_commits": file_commits,
        "groups": groups,
        "rep_commits": rep_commits,
        "rep_display": rep_display,
    }


def persist_repo_to_mongo(
        repo_path: str | Path,
        *,
        mongo_uri: str,
        db: str = "Fork_Technical_Lag",
        coll: str = "test",
        clear_first: bool = False,
        follow_renames: bool = False,
        since: Optional[str] = None,
        include_globs: Optional[List[str]] = None,
) -> str:
    """Build the per-file commit DAGs and persist them under a repo→dir→file hierarchy in MongoDB.

    Returns the `repo_id` (stable across runs for the same absolute repo path).
    """
    data: RepoGraphData = prepare_repo_graph(
        repo_path,
        follow_renames=follow_renames,
        since=since,
        include_globs=include_globs,
    )
    coll_obj = mongo_connect(mongo_uri, db, coll)
    return mongo_persist_hierarchy(
        coll_obj,
        repo=data["repo"],
        rep_display=data["rep_display"],
        groups=data["groups"],
        rep_commits=data["rep_commits"],
        parents=data["parents"],
        meta=data["meta"],
        clear_first=clear_first,
    )


__all__ = [
    "prepare_repo_graph",
    "persist_repo_to_mongo",
    # Utilities below are also useful if you want finer control:
    "build_per_file_edges", "load_commit_parents", "load_commit_meta",
    "load_file_commits", "mongo_connect", "mongo_persist_hierarchy",
]

def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python genere.py <owner/repo> | </absolute/path/to/repo>",
            file=sys.stderr,
        )
        sys.exit(2)

    arg = sys.argv[1]
    p = Path(arg)
    # If user passes owner/repo or relative path, resolve under SELECTED_REPOS_BASE
    if not p.is_absolute():
        # Normalize potential Windows-style separators
        rel = arg.replace("\\", "/")
        p = (SELECTED_REPOS_BASE / rel).resolve()

    repo_id = persist_repo_to_mongo(
        repo_path=p,
        mongo_uri=MONGO_URI,
        db=MONGO_DB,
        coll=MONGO_COLL,
        clear_first=CLEAR_FIRST,
        follow_renames=FOLLOW_RENAMES_DEFAULT,
        since=SINCE_DEFAULT,
        include_globs=INCLUDE_GLOBS_DEFAULT,
    )
    print(f"[ok] persisted repo_id={repo_id} into MongoDB {MONGO_URI}/{MONGO_DB}.{MONGO_COLL}")

if __name__ == "__main__":
    main()