[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](#) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 项目概览

本项目围绕 GitHub 仓库/分叉数据采集、入库（MongoDB）、提交历史处理（提交 DAG / 合并 fork）、统计分析（导出 CSV 报表）与 fork 分类（贡献型/二次开发型）展开。

### 目录结构
- `代码/`：主程序与脚本
  - `collection/`：GitHub 仓库与 forks 采集
  - `importers/`：CSV/JSONL → MongoDB 导入与合并
  - `repo_history/`：仓库克隆与提交历史补全
  - `dag/`：仓库+fork 提交 DAG 构建与入库
  - `file_dag/`：文件级提交 DAG 库（`genere.py`）
  - `analysis/`：统计分析与 fork 分类（含 `fork_analysis/`）
  - `audit/`：PR/提交审计与导出
  - `validation/`：数据验证与研究脚本
- `analysis_results.csv`：统计结果示例

### 依赖
- Python 3.9+，Git（命令行），MongoDB（本地：`mongodb://localhost:27017/`）
- Python 包：`pymongo`、`requests`、`tqdm`、`pandas`、`gitpython`

### 数据流（简化）
1) 采集与导入：`collection/` + `importers/` → `github.repo_with_forks`
2) 历史补全：`repo_history/` → 本地 `selected_repos`
3) DAG 构建：`dag/` → `github.commit_nodes` / `commit_nodes1`
4) 统计分析：`analysis/` → `analysis_results.csv`
5) fork 分类：`analysis/fork_analysis/` → 分类 JSON

### 从 0 到结果（示例）
1) 导入数据（MongoDB）：
```bash
cd 代码/importers
export MONGO_URI=mongodb://localhost:27017/
export ORIGINAL_REPOS_CSV=/path/to/top100_repos.csv
export FORKS_CSV=/path/to/top100_forks.csv
python3 data_importer.py
```

2) 补全提交历史：
```bash
cd 代码/repo_history
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 git_history_collector.py
```

3) 构建提交 DAG（批量）：
```bash
cd 代码/dag
export SELECTED_REPOS_BASE=/abs/path/selected_repos
python3 commit_tree_analyzer.py
```

4) 导出统计：
```bash
cd 代码/analysis
export ANALYSIS_CSV=analysis_results.csv
python3 final_analyzer.py
```

5) 查看示例输出：
```bash
ls examples/analysis_results.csv
```

### 快速开始
1) 导入数据：进入 `importers/` 运行相应脚本
2) 克隆历史：进入 `repo_history/` 运行 `git_history_collector.py`
3) 构建 DAG：进入 `dag/` 运行 `commit_tree_analyzer.py`
4) 导出统计：进入 `analysis/` 运行 `final_analyzer.py`
5) fork 分类：进入 `analysis/fork_analysis/` 运行相关脚本

### 环境与配置

- 复制 `.env.example` 为 `.env` 并按需修改；或直接设置环境变量：
  - `GITHUB_TOKENS`、`GITHUB_TOKEN`（二选一/按需）
  - `SELECTED_REPOS_BASE`、`MONGO_URI` 等

### GitHub 仓库

- 本项目已移除硬编码 Token 和绝对路径；可直接推送到 GitHub。
- 提交前请确保 `.env` 与缓存/大文件未纳入版本控制（见 `.gitignore`）。
test sync 2025年 9月17日 星期三 19时37分54秒 CST
