# 第三问新机制候选与论文复现

本目录将本地 `paper_evidence/q3_mechanism_reset_20260912` 的锁定源码、实验配置、逐例指标、消融和负结果导出到 Git。最终候选为 `GATED_TOUR_MULTI_PARALLAX`。原第三问方法、路线调度、HTTP 入口和 `configs/recommended_omni.json` 均保留，可继续运行和作论文对照。

| 最终自建验证 | 原 BOTH 均值/局 | 新候选均值/局 | 平均降低 | 原/新 P95 | 完整清除 |
|---|---:|---:|---:|---:|---:|
| 有界误差 | 3323.52 秒 | 2982.18 秒 | 10.27% | 4517.29 / 3823.72 秒 | 各 480/480 |
| 舍入压力 | 3319.49 秒 | 2985.19 秒 | 10.07% | 4505.79 / 3827.73 秒 | 各 480/480 |

每例指一整个布局的完整流程；题面“总时间/清除数”的逐局平均为 269.71 → 242.21 秒/源（有界误差）。120 个独立布局各有四种固定误差场，两种舍入；不能把 960 局当作 960 个独立布局。最差配对案例慢 93.63%，原始慢例保留。

- [论文组织、算法取舍与消融口径](PAPER_GUIDE.md)
- [原始最终报告](FINAL_REPORT.md)、[理论依据](THEORY.md)、[对抗式复核](ADVERSARIAL_REVIEW.md)
- [复现命令与两个 HTTP 入口](REPRODUCE.md)
- [最终逐例配对指标](final_paired.csv)、[机器汇总](FINAL_EVIDENCE.json)、[锁定配置](best_candidate.json)
- [验证锁](validation_lock.json)、[导出清单](EXPORT_MANIFEST.json)、[导出与入口验证](EXPORT_VERIFICATION.json)

十轮目录保存动机、代码快照、配置、汇总和放弃原因；`final_validation`、`ablation`、`ablation_expanded` 保存各方案逐例指标。`frozen` 是原方法及依赖的独立快照，论文配对复跑强制使用它，防止日后主目录更新使基线漂移。

逐动作日志、评估器隐藏案例文件和发布 ZIP 留在本地原证据目录；Git 保留可重新生成日志的固定场景、代码和配置，以及原始文件完整 SHA256 索引 `LOCAL_RAW_CHECKSUMS.json.gz`。固定场景仅供评估器，策略不读取。历史报告中的“未推送”描述原探索阶段；本目录是随后按用户要求进行的论文归档提交。导出不改写历史报告和验证锁。

新旧 HTTP 入口共同使用当前 `question3/interface.py`，不另造官方协议；冻结快照只用于论文自建复现。此次仅验证自建环境，未启动官方演练或正式测试；自建收益不代表已通过官方或 Windows 验证。
