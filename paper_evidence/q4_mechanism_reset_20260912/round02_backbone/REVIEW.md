# round02_backbone 开发结论

冻结发现骨架并做源任务最小插入，保护发现顺序；与历史自适应共享组合。

|方案|完整/局数|失败|超时|均值秒|P95秒|最差秒|均值收益|
|---|---:|---:|---:|---:|---:|---:|---:|
|BASE25|96/96|0|0|6857.79|10005.55|10744.02|0.000%|
|HIST_ADAPT|96/96|0|0|6774.57|9867.11|10916.08|1.214%|
|BACKBONE|96/96|0|0|7164.12|10657.11|11597.66|-4.467%|
|BACKBONE_ADAPT|96/96|0|0|6984.75|10074.76|10725.03|-1.851%|

BACKBONE：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_fbe869b0a4890c18__negative__bounded`；最差配对退化 -30.803%。
动作耗时分解（秒/局）：{"detection_s": 1615.0520833333333, "laser_s": 26.666666666666668, "movement_s": 5111.591322992821, "optical_s": 110.40625, "switch_s": 300.40625}
相对基线动作差（秒/局）：{"detection_s": 6.406, "laser_s": 0.0, "movement_s": 289.724, "optical_s": 9.156, "switch_s": 1.042}
机制事件总次数：{"observe": 31009, "feasible_region": 6629, "backbone_insertion": 16024, "optical_cover": 767}

BACKBONE_ADAPT：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_fbe869b0a4890c18__negative__bounded`；最差配对退化 -37.220%。
动作耗时分解（秒/局）：{"detection_s": 1661.9270833333333, "laser_s": 26.666666666666668, "movement_s": 4877.0120699147565, "optical_s": 110.5625, "switch_s": 308.5833333333333}
相对基线动作差（秒/局）：{"detection_s": 53.281, "laser_s": 0.0, "movement_s": 55.145, "optical_s": 9.312, "switch_s": 9.219}
机制事件总次数：{"observe": 31909, "feasible_region": 7524, "backbone_insertion": 17373, "adaptive_attempt": 961, "certified_clear": 1089, "conditional_gate_skip": 811, "shared_attempt": 623, "optical_cover": 186, "optical_route": 186, "optical_step": 2444}

源码/configs、每局 actions.jsonl/strategy.jsonl/result.json 及失败堆栈均位于 development/。上表没有剔除失败、慢例或无触发案例。组合/证书消融不单独计轮。

证据等级：完整性来自保守几何与有限原覆盖/光学兜底；时间收益或退化仅获本开发集实验支持。未证明整局最优，未验证官方分布或官方运行。
