## 4（PR/Commit 审计与导出）

- pr_commit_files_enricher.py：为 PR commit 补充 stats 与 files 详情，写入新集合并导出 CSV。
- pr_commit_files_exporter.py：基于已存明细导出所需报表（命名对齐，脚本内容可继续完善）。
- commit_pr_fork_stats_export.py：合并 `commit_nodes1`、`pr_commit_data`、`repo_with_forks` 导出明细 CSV。
- fork_audit.py / batch_fork_audit.py：fork 审计（单仓/批量）。
- repo_pr_counts.py：仓库 PR 计数导出。
- 贡献行为分析.py / 活跃周期分析.py / 提交内容类型分析.py：行为/周期/内容类型分析脚本。
- api.py：相关统计的 API 辅助（若有）。

依赖：pymongo、requests、pandas、GitHub Token（从环境变量读取更安全）。
