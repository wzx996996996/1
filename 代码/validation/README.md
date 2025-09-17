## validation 目录

包含数据验证、统计检查与中间分析脚本，例如：
- `data_validation.py`, `verification.py`：数据完整性/一致性检查
- `commit_analysis.py`, `commit_timing_analyzer.py`, `advanced_timing_analyzer.py`, `timing_pattern_analyzer.py`：提交与时间模式分析
- `fork_statistics.py`, `fork_commit_analyzer.py`, `lifespan_analyzer.py`, `success_indicator.py`：fork 维度统计与寿命分析
- `csv_processor.py`, `data_analyzer.py`, `data_merger.py`, `data_test.py`：CSV 处理与数据探索
- 中间数据与报告：`fork_lifespan_all_repos.csv`, `repo_family_commit_filtered_simplified.*`, `fork_stat_summary_report.md`

这些脚本主要用于研究与核验，通常不在主流程中批量运行。
