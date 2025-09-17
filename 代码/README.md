## 代码目录使用指南

本目录包含项目的所有可执行脚本与库代码，按照“数据采集 → 导入合并 → 历史补全 → DAG 构建 → 分析/审计”的流水线组织。

通用先决条件：
- Python 3.9+，Git，MongoDB（默认 `mongodb://localhost:27017/`）
- 常用环境变量：`MONGO_URI`、`SELECTED_REPOS_BASE`、`GITHUB_TOKENS`

---

### collection/（仓库与 forks 采集）
- 主要文件：`github_repo_crawler.py`、`github_crawler_test.py`
- 输入：GitHub API
- 输出：`cache/` 下的 JSON/JSONL（含 top repos 与其 forks 列表）
- 依赖：`requests`、有效 `GITHUB_TOKENS`（逗号分隔，可轮换）
- 典型命令：
```bash
cd 代码/collection
export GITHUB_TOKENS=tok1,tok2
python3 github_repo_crawler.py
```

### importers/（导入与合并）
- 主要文件：`data_importer.py`、`repos_forks_importer.py`、`database_importer.py`、`repo_fork_combiner.py`、`simple_importer.py`
- 输入：CSV/JSONL（如 `top100_repos.csv`、`top100_forks.csv`）
- 输出：MongoDB `github.repo_with_forks`（以及示例库 `github_top100` 的 `repos`/`forks`）
- 依赖：`pymongo`、`pandas`（部分脚本）
- 典型命令：
```bash
cd 代码/importers
export MONGO_URI=mongodb://localhost:27017/
export ORIGINAL_REPOS_CSV=/path/to/top100_repos.csv
export FORKS_CSV=/path/to/top100_forks.csv
python3 data_importer.py
```

### repo_history/（本地提交历史补全）
- 主要文件：`git_history_collector.py`
- 输入：`github.repo_with_forks` 中的仓库 URL
- 输出：本地 `selected_repos/owner/repo`（完整历史，带 `.full_history` 标记）
- 依赖：Git、网络连通性
- 典型命令：
```bash
cd 代码/repo_history
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 git_history_collector.py
```

### dag/（提交 DAG 构建）
- 主要文件：`commit_tree_analyzer.py`、`commit_nodes_processor.py`、`commit_tree_100.py`
- 输入：`selected_repos/` 与 `repo_with_forks`
- 输出：MongoDB `commit_nodes` / `commit_nodes1`（按 repo 分块写入）
- 依赖：`pymongo`
- 典型命令：
```bash
cd 代码/dag
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 commit_tree_analyzer.py
```

### analysis/（统计分析与 fork 分类）
- 主要文件：`final_analyzer.py`、`fork_analysis/` 子目录
- 输入：`commit_nodes1`、`pr_commit_data`、`repo_with_forks`
- 输出：`examples/analysis_results.csv` 与分类 JSON
- 依赖：`pymongo`、（可选）`pandas`
- 典型命令：
```bash
cd 代码/analysis
export ANALYSIS_CSV=analysis_results.csv
python3 final_analyzer.py
```

### file_dag/（文件级 DAG 库）
- 主要文件：`genere.py`
- 输入：单个仓库工作副本
- 输出：将“仓库→目录→文件”的层级与每个文件的精简 commit-graph 持久化到 Mongo
- 依赖：`pymongo`
- 典型命令：
```bash
cd 代码/file_dag
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 genere.py owner/repo
```

### audit/（PR/提交审计）
- 主要文件：`pr_commit_files_enricher.py`、`fork_audit.py`、`batch_fork_audit.py`
- 输入：`pr_commit_data`（或数据库内 PR 明细）、GitHub API
- 输出：增强后的明细集合与 CSV（含 stats/files）
- 依赖：`pymongo`、`requests`、`tqdm`（可选）
- 典型命令：
```bash
cd 代码/audit
export GITHUB_TOKENS=tok1,tok2
python3 pr_commit_files_enricher.py
```

### validation/（验证与研究脚本）
- 主要文件：时间模式/寿命/贡献等统计脚本
- 说明：用于研究与核验，不在主流程批量执行；可按需运行及参考其中的分析方法

---

提示：
- 若遇到速率限制/权限问题，请设置 `GITHUB_TOKENS` 并确保 Token 具备 `Contents: Read & write`（Fine-grained）或 `public_repo/repo`（Classic）。
- Mongo 集合规模较大时，建议为 `repo_id`、`PR Number`、`repo` 等字段建立索引以提升性能。
