# 最优组合的移除消融（不是新一轮机制）

开发选择规则仍不变，已入围四个版本的代码行为不变。这里将GATED_TOUR_SHARED_PARALLAX逐项移除：

- GATED_TOUR_SHARED：去掉视差探测点，保留集合中心逼近。
- TOUR_REFRESH_PARALLAX：去掉跨频道共享观测。
- GATED_TOUR_MULTI_PARALLAX：去掉切换任务时的目标原地再观测，保留移动后的跨频道共享。
- GATED_NEAREST_SHARED_PARALLAX：去掉全行程2-opt，只按集合中心入口最近。
- TOUR_SHARED_PARALLAX：去掉所有输出收缩门控（已在R9和扩展开发直接对照）。

先在52个原开发案例、两种舍入下运行。消融只为判断贡献，不追加参数搜索；最终验证可以运行全部锁定的消融，不能在看到验证结果后改选其中一个。各自耗时分解与逐例日志完整保留。
