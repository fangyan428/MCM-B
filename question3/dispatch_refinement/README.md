# 第三问调度优化尝试：保留当前正式候选

2026-09-13，针对“搜索顺序未考虑剩余源发现价值、路线成本没有计入源服务”的不足，实现并比较四种独立调度候选。**本轮未找到达到采用门槛的改进，继续使用论文当前的 `GATED_TOUR_MULTI_PARALLAX`。** 原创新策略、配置和HTTP入口均未修改；本目录不接入官方运行入口。

## 对照与结果

主对照CURRENT就是当前创新方案，不是更早的round19 BOTH。开发矩阵包含42个新物理布局：六类场景分别覆盖源数10至16；每布局四种固定误差和两种舍入。每个方案336次运行，五方案共1680次，全部完整清除；199870条接受动作通过独立计时、物理与停止审计，位置更新也通过真源包含核验。另完成7项针对性测试和10次自建模拟器流程检查。

下表为同批配对的平均虚拟总时间变化，正数表示比CURRENT慢，负数表示节省。

| 方案 | 实际改动 | 有界误差 | 舍入压力 |
|---|---|---:|---:|
| COVERAGE_ORDER | 保留搜索/服务决定，按未知区域覆盖收益重排搜索站 | +1.54% | +1.34% |
| COVERAGE_PRIORITY | 同时按估计发现收益与服务收益决定下一任务 | +16.66% | +16.47% |
| SERVICE_PAIR | 加入服务费用与实际首动作点，只规划前两项任务 | +7.26% | +7.04% |
| SERVICE_TOUR | 将服务费用与结束位置代理加入完整滚动路线 | -0.24% | -0.64% |

表现最好的是SERVICE_TOUR，但收益很小且尾部增加。有界误差下，CURRENT/候选均值为3091.88/3084.43秒，P95为4102.99/4105.32秒，最大值为4211.04/4327.16秒。以42个布局为块的描述性95%收益区间为[-1.04%,1.51%]，舍入压力为[-0.67%,2.02%]，均跨过零。这些区间来自开发比较，不能当作预选后独立验证。

SERVICE_TOUR也没有解决逐局退化：本批最差相对案例 `dispatch_development_radial_2026091334_spatial_hash` 从1820.65秒增加到2745.60秒，慢50.80%，两者均清除16源。有界误差下聚集类均值改善4.74%，但接收边界类慢2.67%；12源层均值慢0.28%。总体每源平均值改善不代表每个源数层都改善。完整类别、源数和误差分解见analysis.json。

## 为什么没有采用

覆盖面积只是未知位置的粗略排序依据，不能准确预测真实源出现在哪里。COVERAGE_ORDER平均多走约48.97秒，COVERAGE_PRIORITY多走约503.20秒，新增发现排序没有抵消绕行。SERVICE_PAIR虽然减少部分检测，却平均增加234.18秒移动，说明只看两项任务损失了整体行程安排。

SERVICE_TOUR的服务建模更细，但仍不知道实际定位终点及未来观测。它平均减少11.62秒移动，同时增加约4.17秒检测与切频，净省7.46秒；计算耗时P95也由约0.21秒增加至0.62秒。其几何安全性没有问题，现有收益不足以支持在正式测试前替换。

按[事前协议](PROTOCOL.md)，开发须平均时间降低且P95/最大值不升，才会选择一个候选进入新验证。本轮没有合格者，selection_lock.json的selected为null，因此没有运行预定84布局验证，也没有针对结果改参、改选或扩大候选集合。不能把开发中的微小均值下降报告成已验证的优化成果。

## 可复核材料与范围

- [开发汇总](../results/dispatch_20260913/development/summary.json)：逐案例完整指标、审计状态及汇总。
- [分组分析](../results/dispatch_20260913/development/analysis.json)：均值、P95、最大值、源数/类别/误差分层、布局级区间。
- [配对数据](../results/dispatch_20260913/development/paired.csv)：全部候选与CURRENT逐例差异。
- [开发源码与环境索引](../results/dispatch_20260913/development/metadata.json)、[选择锁](../results/dispatch_20260913/selection_lock.json)、code_snapshot：用于核对实际运行版本。
- 原始actions.jsonl、strategy.jsonl、result.json、evaluator_hidden_case.json保留在本地对应案例目录，不上传Git。

已有汇总可直接重新分析：

```text
python -m question3.dispatch_refinement.analyze --stage development
python -m unittest question3.dispatch_refinement.test_discovery question3.dispatch_refinement.test_service -v
```

完整重放入口为 `python -m question3.dispatch_refinement.experiment --stage development --workers 4`，会拒绝覆盖已有输出；应在独立工作副本中保留旧材料后运行，并将其称为已见开发布局的重放。策略只获得PublicClient和公开状态；场景源数/类别及真值仅用于生成和事后核验。

本轮没有启动官方模拟器、演练或正式测试，没有将这些开发数值写入论文的正式成绩表。原冻结源码95项及当前运行依赖已核对。本轮建议是保持当前方案，接下来完成正式运行入口与版本记录。
