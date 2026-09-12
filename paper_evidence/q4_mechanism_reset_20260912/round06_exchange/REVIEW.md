# round06_exchange 开发结论

真实到达点替代未访站，整域连续证书保底；三角证书作为收紧的消融。

|方案|完整/局数|失败|超时|均值秒|P95秒|最差秒|均值收益|
|---|---:|---:|---:|---:|---:|---:|---:|
|BASE25|96/96|0|0|6857.79|10005.55|10744.02|0.000%|
|HIST_ADAPT|96/96|0|0|6774.57|9867.11|10916.08|1.214%|
|COVER_EXCHANGE|96/96|0|0|6840.25|10005.55|10744.02|0.256%|
|COVER_EXCHANGE_TRI|96/96|0|0|6833.14|10005.55|10744.02|0.360%|

COVER_EXCHANGE：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_3b514d2d38d2a25c__smooth__bounded`；最差配对退化 -19.299%。
动作耗时分解（秒/局）：{"detection_s": 1613.1770833333333, "laser_s": 26.666666666666668, "movement_s": 4805.061404126362, "optical_s": 95.03125, "switch_s": 300.3125}
相对基线动作差（秒/局）：{"detection_s": 4.531, "laser_s": 0.0, "movement_s": -16.806, "optical_s": -6.219, "switch_s": 0.948}
机制事件总次数：{"observe": 30973, "optical_cover": 685, "coverage_exchange": 20}

COVER_EXCHANGE_TRI：未达到 5% / 成功率 / P95 联合门槛；不替换推荐。
最差绝对案例 `outward_3b514d2d38d2a25c__smooth__bounded`；最差配对退化 -19.299%。
动作耗时分解（秒/局）：{"detection_s": 1611.0416666666667, "laser_s": 26.666666666666668, "movement_s": 4801.5841233513975, "optical_s": 94.0, "switch_s": 299.84375}
相对基线动作差（秒/局）：{"detection_s": 2.396, "laser_s": 0.0, "movement_s": -20.283, "optical_s": -7.25, "switch_s": 0.479}
机制事件总次数：{"observe": 30932, "optical_cover": 687, "coverage_exchange": 18}

源码/configs、每局 actions.jsonl/strategy.jsonl/result.json 及失败堆栈均位于 development/。上表没有剔除失败、慢例或无触发案例。组合/证书消融不单独计轮。

证据等级：完整性来自保守几何与有限原覆盖/光学兜底；时间收益或退化仅获本开发集实验支持。未证明整局最优，未验证官方分布或官方运行。
