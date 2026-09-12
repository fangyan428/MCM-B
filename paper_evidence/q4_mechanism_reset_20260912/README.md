# B题第四问：机制重新探索（2026-09-12）

**没有找到满足5%门槛的显著改进，不建议替换当前25站推荐。** 十轮核心机制及组合筛选后锁定的动态替站＋受覆盖约束的测站移动，在120个独立新布局上仅平均省时0.366%，P95降低0.394%；收益95%区间跨零。开发、对抗和最终确认共8608次完整流程自建运行，全部清除、无失败或超时。

- [最终报告](FINAL_REPORT.md)：完整流程对照、消融、十轮负结果、最坏案例、证据等级与建议。
- [锁定候选](best_candidate.json)／[候选代码](coverage.py)：只保留为实验方案，没有覆盖当前推荐。
- [最终统计](FINAL_STATISTICS.json)／[总证据](FINAL_EVIDENCE.json)／[数据隔离核验](PROVENANCE_CHECK.json)。
- [原题与历史审查](SOURCE_AUDIT.md)／[最终对抗复核](qa/FINAL_ADVERSARIAL_REVIEW.md)。
- [事前协议](PROTOCOL.md)／[候选选择](SELECTION.md)／[验证锁](validation_lock/lock.json)。
- [逐轮索引](round_index.json)：每轮 README、REVIEW、完整配置/源码快照/动作日志/结果在独立 round*/development/。
- [复现说明](REPRODUCE.md)／[公共响应重放](qa/REPLAY.md)。

总算法运行数不是独立布局数。最终4800次运行是120布局×4固定误差场×2舍入×5臂。自建记录不充作官方演练或正式测试结果。本轮不推送云端，不修改原推荐。
