## 审计与导出（audit/）

当前可用脚本：
- `pr_commit_files_enricher.py`：为 PR commit 补充 stats 与 files 详情，写入新集合并导出 CSV。
- `fork_audit.py` / `batch_fork_audit.py`：fork 审计（单仓/批量）。
- `repo_pr_commit_summary.py`：按仓库统计唯一 PR 数与 PR 提交总数，导出 CSV。

依赖：`pymongo`、`requests`、`tqdm`（可选）、GitHub Token（从环境变量读取更安全）。

### 环境变量
- `GITHUB_TOKENS`：逗号分隔的多个 GitHub Token，用于提升 API 速率上限
- `MONGO_URI`：Mongo 连接串（默认 `mongodb://localhost:27017/`）

### 运行示例
为 PR 提交补充文件级明细并导出：
```bash
cd 代码/audit
export GITHUB_TOKENS=tok1,tok2
python3 pr_commit_files_enricher.py
```

批量 fork 审计（需本地仓库与 `repo_with_forks`）：
PR 汇总导出：
```bash
cd 代码/audit
export PR_SUMMARY_CSV=repo_pr_commit_summary.csv
python3 repo_pr_commit_summary.py
```
```bash
cd 代码/audit
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 batch_fork_audit.py
```
