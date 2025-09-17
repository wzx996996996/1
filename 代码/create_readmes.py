# /Users/wzx/Downloads/Pycharm Project/项目/代码/create_readmes.py
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent
ROOT = CODE.parent
VERIFY = CODE / "validation"
FORK = CODE / "analysis" / "fork_analysis"

files = {
    # 顶层 README
    ROOT / "README.md": '''## 项目概览

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

### 快速开始
1) 导入数据：进入 `importers/` 运行相应脚本
2) 克隆历史：进入 `repo_history/` 运行 `git_history_collector.py`
3) 构建 DAG：进入 `dag/` 运行 `commit_tree_analyzer.py`
4) 导出统计：进入 `analysis/` 运行 `final_analyzer.py`
5) fork 分类：进入 `analysis/fork_analysis/` 运行相关脚本
''',

    # 代码目录 README（含 fork_analysis）
    CODE / "README.md": '''## 代码目录索引与用途

- collection/：`github_repo_crawler.py`、`github_crawler_test.py`
- importers/：`data_importer.py`、`repos_forks_importer.py`、`database_importer.py`、`repo_fork_combiner.py`、`simple_importer.py`
- repo_history/：`git_history_collector.py`
- dag/：`commit_nodes_processor.py`、`commit_tree_analyzer.py`、`commit_tree_100.py`
- analysis/：`final_analyzer.py`、`fork_analysis/`
- file_dag/：`genere.py`
- audit/：PR/提交审计导出脚本
- validation/：验证/研究脚本与中间数据

建议先阅读各脚本 README，按需配置路径/环境变量后运行。
''',

    # 确认问题 README（索引）
    VERIFY / "README.md": '''## validation 目录

包含数据验证、统计检查与中间分析脚本，例如：
- `data_validation.py`, `verification.py`：数据完整性/一致性检查
- `commit_analysis.py`, `commit_timing_analyzer.py`, `advanced_timing_analyzer.py`, `timing_pattern_analyzer.py`：提交与时间模式分析
- `fork_statistics.py`, `fork_commit_analyzer.py`, `lifespan_analyzer.py`, `success_indicator.py`：fork 维度统计与寿命分析
- `csv_processor.py`, `data_analyzer.py`, `data_merger.py`, `data_test.py`：CSV 处理与数据探索
- 中间数据与报告：`fork_lifespan_all_repos.csv`, `repo_family_commit_filtered_simplified.*`, `fork_stat_summary_report.md`

这些脚本主要用于研究与核验，通常不在主流程中批量运行。
''',

    # 主流程脚本 README（保持原有）
    CODE / "collection" / "github_repo_crawler.README.md": '''## collection/github_repo_crawler.py
...（同前，已包含：功能/依赖/安全提示/配置/运行/输出）...''',
    CODE / "importers" / "data_importer.README.md": '''## importers/data_importer.py
...''',
    CODE / "importers" / "repo_fork_combiner.README.md": '''## importers/repo_fork_combiner.py
...''',
    CODE / "importers" / "repos_forks_importer.README.md": '''## importers/repos_forks_importer.py
...''',
    CODE / "importers" / "database_importer.README.md": '''## importers/database_importer.py
...''',
    CODE / "repo_history" / "git_history_collector.README.md": '''## repo_history/git_history_collector.py
...''',
    CODE / "dag" / "commit_nodes_processor.README.md": '''## dag/commit_nodes_processor.py
...''',
    CODE / "dag" / "commit_tree_analyzer.README.md": '''## dag/commit_tree_analyzer.py
...''',
    CODE / "analysis" / "final_analyzer.README.md": '''## analysis/final_analyzer.py
...''',
    CODE / "importers" / "simple_importer.README.md": '''## importers/simple_importer.py
...''',
    CODE / "file_dag" / "genere.README.md": '''## file_dag/genere.py
...''',
    CODE / "dag" / "commit_tree_100.README.md": '''## dag/commit_tree_100.py
...''',
    CODE / "collection" / "github_crawler_test.README.md": '''## collection/github_crawler_test.py
...''',
    CODE / "analysis" / "data_test.README.md": '''## analysis/data_test.py
...''',
}

# fork_analysis 目录与 README（支持你已重命名的结构）
files.update({
    FORK / "README.md": '''## fork_analysis 目录说明（Fork 分类与示例）

依赖 Git 完整历史与 MongoDB `repo_with_forks`。
- 公共前置：`BASE_DIR`（本地完整仓库根）、`mongodb://localhost:27017/`、`github.repo_with_forks`
- 依赖：Git、GitPython（`pip install gitpython`）、`pymongo`、`tqdm`

### 内容
- `classify_forks.py`：按提交集合判定「贡献型」与「二次开发型」，输出总体分类 JSON（`classification_results.json`）。
- `types_summary.py`：统计 Type 1/2/3 数量（打印）。
- `types_effective_stats.py`：在统计基础上剔除缺失/不可读 fork（打印实际有效指标）。
- `export_pure_contribution.py`：导出纯贡献型 fork（`pure_contribution.json`）。
- `extract_secondary_examples.py`：抽取若干二次开发型示例（`secondary_examples.json`）。
''',
    FORK / "classify_forks.README.md": '''## fork_analysis/classify_forks.py
...''',
    FORK / "types_summary.README.md": '''## fork_analysis/types_summary.py
...''',
    FORK / "types_effective_stats.README.md": '''## fork_analysis/types_effective_stats.py
...''',
    FORK / "export_pure_contribution.README.md": '''## fork_analysis/export_pure_contribution.py
...''',
    FORK / "extract_secondary_examples.README.md": '''## fork_analysis/extract_secondary_examples.py
...''',
})

# 若你尚未执行重命名脚本，仍然保留「旧文件名」的 README（避免空档期无法查阅）
files.update({
    FORK / "fork_classification.README.md": '''## fork_analysis/fork_classification.py
（若你尚未重命名脚本，等价于：classify_forks.py）
...''',
    FORK / "1.README.md": '''## fork_analysis/1.py
（尚未重命名时的统计脚本，等价于：types_summary.py）
...''',
    FORK / "2.README.md": '''## fork_analysis/2.py
（尚未重命名时的有效统计脚本，等价于：types_effective_stats.py）
...''',
    FORK / "3.README.md": '''## fork_analysis/3.py
（尚未重命名时的导出脚本，等价于：export_pure_contribution.py）
...''',
    FORK / "secondary_dev_examples.README.md": '''## fork_analysis/secondary_dev_examples.py
（尚未重命名时的示例脚本，等价于：extract_secondary_examples.py）
...''',
})

def main():
    for d in [ROOT, CODE, VERIFY, FORK]:
        d.mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Wrote: {path}")
    print("🎉 All READMEs generated/refreshed.")

if __name__ == "__main__":
    main()