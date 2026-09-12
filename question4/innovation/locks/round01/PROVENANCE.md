# R1选择锁溯源补充

此处lock从 `results/round01_dev/lock.json` 复制源码和配置摘要，再绑定 `ROUND01_DECISION.md`。其 `error_modes` / `roundings` 字段保留了开发批的2×1，`prior_lock`未更新。原文件保留，不能重写历史证据。

真正的事前独立验证设计由本锁绑定的selection_snapshot.txt指定：seed151000、48布局、四误差×两舍入。执行批 `results/round01_validation/lock.json` 与metadata.json正确记载4×2，包含本选择锁的SHA256。检查确认配置/源码/选择SHA一致、2688局矩阵完整、源码运行期间未变，且与所有此前第四问fixture无布局重叠；因此该元数据笔误不改变实际试验。

后续选择锁直接构建并显式记录父批路径、摘要和完整实验设计，不再复制整份开发锁。
