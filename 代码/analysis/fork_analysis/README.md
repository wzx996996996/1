## fork_analysis 目录说明（Fork 分类与示例）

依赖 Git 完整历史与 MongoDB `repo_with_forks`。
- 公共前置：`BASE_DIR`（本地完整仓库根）、`mongodb://localhost:27017/`、`github.repo_with_forks`
- 依赖：Git、GitPython（`pip install gitpython`）、`pymongo`、`tqdm`

### 内容
- `classify_forks.py`：按提交集合判定「贡献型」与「二次开发型」，输出总体分类 JSON（`classification_results.json`）。
- `types_summary.py`：统计 Type 1/2/3 数量（打印）。
- `types_effective_stats.py`：在统计基础上剔除缺失/不可读 fork（打印实际有效指标）。
- `export_pure_contribution.py`：导出纯贡献型 fork（`pure_contribution.json`）。
- `extract_secondary_examples.py`：抽取若干二次开发型示例（`secondary_examples.json`）。
