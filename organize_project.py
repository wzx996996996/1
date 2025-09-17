# /Users/wzx/Downloads/Pycharm Project/项目/organize_project.py
import os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODE = ROOT / "代码"
FA   = CODE / "fork_analysis"  # 旧 3/ 已迁移到此
D4   = ROOT / "4"

def rm(p: Path):
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    except Exception:
        pass

def mv(src: Path, dst: Path):
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    src.rename(dst)

def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def replace_in_file(p: Path, repl: dict):
    if not p.exists() or not p.is_file():
        return
    s = p.read_text(encoding="utf-8")
    changed = False
    for k,v in repl.items():
        if k in s:
            s = s.replace(k,v); changed = True
    if changed:
        p.write_text(s, encoding="utf-8")

# ---------- 1) 清理杂项 ----------
for junk in [
    CODE / ".DS_Store",
    CODE / "rename_and_update",
]:
    rm(junk)

# ---------- 2) fork_analysis 规范化（文件重命名 + JSON 文件名统一 + README） ----------
fa_map = {
    "fork_classification.py": "classify_forks.py",
    "1.py": "types_summary.py",
    "2.py": "types_effective_stats.py",
    "3.py": "export_pure_contribution.py",
    "secondary_dev_examples.py": "extract_secondary_examples.py",
}
json_map = {
    "fork_classification_results.json": "classification_results.json",
    "pure_contribution_forks.json": "pure_contribution.json",
    "secondary_dev_examples.json": "secondary_examples.json",
}
if (CODE / "3").exists() and not FA.exists():
    mv(CODE/"3", FA)

FA.mkdir(parents=True, exist_ok=True)
# 脚本改名
for old, new in fa_map.items():
    mv(FA/old, FA/new)
# JSON 改名 + 同步替换脚本中的输出文件名
for old, new in json_map.items():
    mv(FA/old, FA/new)
for py in FA.glob("*.py"):
    replace_in_file(py, json_map)

# 目录 README
write(FA/"README.md", """## fork_analysis（Fork 分类与示例）

- classify_forks.py：按提交集合判定贡献型/二次开发型 → classification_results.json
- types_summary.py：统计 Type 1/2/3（打印）
- types_effective_stats.py：在统计基础上剔除缺失/不可读 fork（打印）
- export_pure_contribution.py：导出纯贡献型 → pure_contribution.json
- extract_secondary_examples.py：抽取二次开发型示例 → secondary_examples.json

依赖：Git、GitPython、pymongo、tqdm；数据源：`github.repo_with_forks`；本地仓库根 `BASE_DIR`。
""")

# 为各脚本生成 README（就近）
fa_readmes = {
"classify_forks": """## classify_forks.py
- 功能：对比 fork 与父仓提交集，输出分类到 `classification_results.json`。
- 运行：python3 fork_analysis/classify_forks.py
""",
"types_summary": """## types_summary.py
- 功能：统计 Type 1/2/3 数量（打印）。
- 运行：python3 fork_analysis/types_summary.py
""",
"types_effective_stats": """## types_effective_stats.py
- 功能：在统计基础上剔除缺失/不可读 fork，打印“实际有效”指标。
- 运行：python3 fork_analysis/types_effective_stats.py
""",
"export_pure_contribution": """## export_pure_contribution.py
- 功能：导出纯贡献型 fork 到 `pure_contribution.json`。
- 运行：python3 fork_analysis/export_pure_contribution.py
""",
"extract_secondary_examples": """## extract_secondary_examples.py
- 功能：输出若干二次开发型示例到 `secondary_examples.json`。
- 运行：python3 fork_analysis/extract_secondary_examples.py
""",
}
for stem, content in fa_readmes.items():
    write(FA/f"{stem}.README.md", content)

# ---------- 3) 代码目录下脚本 README 对齐（若缺则补齐） ----------
main_readmes = {
"github_repo_crawler.py": """## github_repo_crawler.py
- 功能：按语言抓取 Top 仓库及 forks（缓存/断点续抓）。
- 运行：python3 代码/github_repo_crawler.py
""",
"data_importer.py": """## data_importer.py
- 功能：导入原始仓库 CSV 与 fork TSV 到 `github.repo_with_forks`。
- 运行：python3 代码/data_importer.py
""",
"repo_fork_combiner.py": """## repo_fork_combiner.py
- 功能：合并 `repos` 与 `forks` → `repo_with_forks`。
- 运行：python3 代码/repo_fork_combiner.py
""",
"repos_forks_importer.py": """## repos_forks_importer.py
- 功能：导入 CSV 到示例库 `github_top100` 的 `repos`/`forks`。
- 运行：python3 代码/repos_forks_importer.py
""",
"database_importer.py": """## database_importer.py
- 功能：导入 PR 提交数据 CSV → `github.pr_commit_data`。
- 运行：python3 代码/database_importer.py
""",
"git_history_collector.py": """## git_history_collector.py
- 功能：浅克隆→unshallow 补全历史；完成标记 `.full_history`；失败记录。
- 运行：python3 代码/git_history_collector.py
""",
"commit_nodes_processor.py": """## commit_nodes_processor.py
- 功能：单仓库+forks 构建提交 DAG → `github.commit_nodes`。
- 运行：python3 代码/commit_nodes_processor.py
""",
"commit_tree_analyzer.py": """## commit_tree_analyzer.py
- 功能：批量构建提交 DAG → `github.commit_nodes1`。
- 运行：python3 代码/commit_tree_analyzer.py
""",
"commit_tree_100.py": """## commit_tree_100.py
- 功能：示例性批量构建（限前 100 仓库）→ `github.commit_nodes1`。
- 运行：python3 代码/commit_tree_100.py
""",
"final_analyzer.py": """## final_analyzer.py
- 功能：综合统计输出 `analysis_results.csv`。
- 运行：python3 代码/final_analyzer.py
""",
"genere.py": """## genere.py
- 功能：文件级精简提交 DAG（库函数）。
- 用法：见文件内示例。
""",
"github_crawler_test.py": """## github_crawler_test.py
- 功能：Search API 测试抓取（JSONL）。
- 运行：python3 代码/github_crawler_test.py
""",
"data_test.py": """## data_test.py
- 功能：快速统计共享提交计数（`from_repo` 长度>1）。
- 运行：python3 代码/data_test.py
""",
}
for fn, md in main_readmes.items():
    p = CODE/fn
    if p.exists():
        write(CODE/f"{Path(fn).stem}.README.md", md)

# ---------- 4) /项目 根下脚本与 4/ 目录整理 ----------
# 根 4.py → 4/commit_pr_fork_stats_export.py
mv(ROOT/"4.py", D4/"commit_pr_fork_stats_export.py")

# 4/ 下不清晰文件名重命名
d4_map = {
    "1.py": "pr_commit_files_enricher.py",        # PR commit 补充文件级别修改
    "2.py": "pr_commit_files_exporter.py",        # 可能的导出/汇总（命名更语义）
    "Python 脚本版.py": "manual_script_version.py",
}
for old, new in d4_map.items():
    mv(D4/old, D4/new)

# 4/ 目录级 README
write(D4/"README.md", """## 4（PR/Commit 审计与导出）

- pr_commit_files_enricher.py：为 PR commit 补充 stats 与 files 详情，写入新集合并导出 CSV。
- pr_commit_files_exporter.py：基于已存明细导出所需报表（命名对齐，脚本内容可继续完善）。
- commit_pr_fork_stats_export.py：合并 `commit_nodes1`、`pr_commit_data`、`repo_with_forks` 导出明细 CSV。
- fork_audit.py / batch_fork_audit.py：fork 审计（单仓/批量）。
- repo_pr_counts.py：仓库 PR 计数导出。
- 贡献行为分析.py / 活跃周期分析.py / 提交内容类型分析.py：行为/周期/内容类型分析脚本。
- api.py：相关统计的 API 辅助（若有）。

依赖：pymongo、requests、pandas、GitHub Token（从环境变量读取更安全）。
""")

# 4/ 各关键脚本 README（就近）
d4_readmes = {
"pr_commit_files_enricher.py": """## pr_commit_files_enricher.py
- 功能：从 `pr_commit_data` 读取，调用 GitHub API 获取 stats+files；写入新表并导出 CSV。
- 运行：python3 4/pr_commit_files_enricher.py
""",
"pr_commit_files_exporter.py": """## pr_commit_files_exporter.py
- 功能：基于已存文件级明细导出统计报表（请按需求补充具体导出字段）。
- 运行：python3 4/pr_commit_files_exporter.py
""",
"commit_pr_fork_stats_export.py": """## commit_pr_fork_stats_export.py
- 功能：合并 `commit_nodes1`、`pr_commit_data`、`repo_with_forks` 导出 CSV。
- 运行：python3 4/commit_pr_fork_stats_export.py
""",
"fork_audit.py": """## fork_audit.py
- 功能：审计指定仓库/集合中的 fork 关系与贡献行为（请在脚本内配置参数）。
- 运行：python3 4/fork_audit.py
""",
"batch_fork_audit.py": """## batch_fork_audit.py
- 功能：批量执行 fork 审计，输出合并结果或报表。
- 运行：python3 4/batch_fork_audit.py
""",
"repo_pr_counts.py": """## repo_pr_counts.py
- 功能：统计仓库 PR 数并导出 CSV。
- 运行：python3 4/repo_pr_counts.py
""",
"贡献行为分析.py": """## 贡献行为分析.py
- 功能：分析贡献行为并导出相关 CSV。
- 运行：python3 4/贡献行为分析.py
""",
"活跃周期分析.py": """## 活跃周期分析.py
- 功能：分析贡献活跃周期并导出相关 CSV。
- 运行：python3 4/活跃周期分析.py
""",
"提交内容类型分析.py": """## 提交内容类型分析.py
- 功能：分析提交内容类型（如文件类型/更改规模）并导出 CSV。
- 运行：python3 4/提交内容类型分析.py
""",
"api.py": """## api.py
- 功能：提供统计/查询相关的 API 辅助（如有）。
- 运行：python3 4/api.py
""",
"manual_script_version.py": """## manual_script_version.py
- 功能：原“Python 脚本版”，保留为手工流程/临时脚本。
- 运行：python3 4/manual_script_version.py
""",
}
for fn, md in d4_readmes.items():
    p = D4/fn
    if p.exists():
        write(D4/f"{Path(fn).stem}.README.md", md)

# ---------- 5) 顶层 README 轻微刷新（如缺少 fork_analysis/ 或 4/ 提示则追加） ----------
top = ROOT/"README.md"
if top.exists():
    s = top.read_text(encoding="utf-8")
    if "fork_analysis/" not in s:
        s = s.replace("fork 分类：`fork_analysis/`", "fork 分类：`fork_analysis/`（见目录内 README）")
    if "- `analysis_results.csv`" not in s and (CODE/"analysis_results.csv").exists():
        s += "\n- `analysis_results.csv`：统计结果示例\n"
    top.write_text(s, encoding="utf-8")

print("✅ 项目整理完成：重命名/清理/README 已更新。")