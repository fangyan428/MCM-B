# round07_elastic 开发结论

联合优化未访内站位置与路径；与到达点替站组合。

|方案|完整/局数|失败|超时|均值秒|P95秒|最差秒|均值收益|
|---|---:|---:|---:|---:|---:|---:|---:|
|BASE25|96/96|0|0|6857.79|10005.55|10744.02|0.000%|
|HIST_ADAPT|96/96|0|0|6774.57|9867.11|10916.08|1.214%|
|COVER_ELASTIC|96/96|0|0|6710.38|9947.34|10685.79|2.150%|
|COVER_EXCHANGE_ELASTIC|96/96|0|0|6698.13|9947.34|10685.79|2.328%|

COVER_ELASTIC：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_3b514d2d38d2a25c__smooth__bounded`；最差配对退化 -17.878%。
动作耗时分解（秒/局）：{"detection_s": 1605.9375, "laser_s": 26.666666666666668, "movement_s": 4675.636336669172, "optical_s": 102.9375, "switch_s": 299.1979166666667}
相对基线动作差（秒/局）：{"detection_s": -2.708, "laser_s": 0.0, "movement_s": -146.231, "optical_s": 1.688, "switch_s": -0.167}
机制事件总次数：{"observe": 30834, "coverage_elastic": 1111, "optical_cover": 740}

COVER_EXCHANGE_ELASTIC：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_3b514d2d38d2a25c__smooth__bounded`；最差配对退化 -17.878%。
动作耗时分解（秒/局）：{"detection_s": 1605.7291666666667, "laser_s": 26.666666666666668, "movement_s": 4671.675197629943, "optical_s": 95.0625, "switch_s": 299.0}
相对基线动作差（秒/局）：{"detection_s": -2.917, "laser_s": 0.0, "movement_s": -150.192, "optical_s": -6.188, "switch_s": -0.365}
机制事件总次数：{"observe": 30830, "coverage_elastic": 1052, "optical_cover": 735, "coverage_exchange": 12}

源码/configs、每局 actions.jsonl/strategy.jsonl/result.json 及失败堆栈均位于 development/。上表没有剔除失败、慢例或无触发案例。组合/证书消融不单独计轮。

证据等级：完整性来自保守几何与有限原覆盖/光学兜底；时间收益或退化仅获本开发集实验支持。未证明整局最优，未验证官方分布或官方运行。
