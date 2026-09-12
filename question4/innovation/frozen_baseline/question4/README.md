# 第四问：混合全向／定向源

推荐配置为 `configs/recommended.json`：**25站双环覆盖 + 定位区域重心调度 + 低信息检测删减 + 16源已知上界停止 + 交会／光学完整性兜底**。

最终两批各96个新布局全部完成清除，整局总虚拟时间比31站初始基线平均降低 **41.83% / 41.24%**。整个研发共15批、5376局自建配对运行，均完整清除并通过逐动作物理、计时和停止证书审计。5376是算法运行次数，包含对照与开发集重用，不是5376个独立布局。

已按用户约定停止继续优化。后续机制的独立验证收益低于约1%或为负，详见 [最终实验结论](docs/最终方案与实验结论.md)、[完整性证明](docs/模型与完整性证明.md) 和 [失败与负结果](docs/失败与负结果.md)。不宣称全局最优。

官方演练、三次正式测试和Windows实测均未执行。自建结果不能填入官方正式测试表。

## 运行

在项目根目录安装依赖：

```bash
python -m pip install -r question4/requirements.txt
```

本机自建HTTP环境分两个终端运行：

```bash
python -m question4.self_server --seed 0 --family outward
```

```bash
python -m question4.run_http --mode self-http --output question4/results/my_self_http
```

使用新输出目录，避免覆盖原始证据。接口默认127.0.0.1:2028；该服务不访问官方环境。

在Windows启动官方模拟器，登录并选择**问题4演练测试**，待界面显示接口就绪后，在项目根目录执行：

```text
python -m question4.run_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --output question4/results/windows_q4_rehearsal_001
```

默认连接127.0.0.1:2026；队号必须与实际登录账号一致。四条API不能识别界面模式，确认标志不是技术鉴别。当前入口没有正式测试模式，不会自动启动官方程序或点击测试按钮。演练结束后需从界面记录真实总数、清除数、案例编码和官方运行时间，并核对自有日志；接口未提供的官方总数保留为null。

## 独立实验复现

```bash
python -m question4.experiment --configs question4/configs/round9_validation.json --output question4/results/reproduce_round9_main --fixtures question4/results/round9_main/fixtures.json --lock question4/results/round9_main/lock.json --stage reproduction_not_new_validation
```

复现舍入压力批次应替换fixture和lock路径，增加 `--rounding pre_round_stress`。复用旧fixture是复现，不是新独立验证。历史源码变更时应恢复该批 `code_snapshot/` 到独立目录后运行，不要修改原始锁文件。

生成新的独立布局：

```bash
python -m question4.experiment --configs question4/configs/round9_validation.json --output question4/results/new_validation --seed 131000 --count 96 --error-modes spatial_hash,positive,negative,smooth --stage new_independent_validation
```

运行器先持久化源码和配置锁，再生成案例；隐藏布局只传入环境，策略仅收到四条API的响应。`audit.py` 在策略结束后才读取真值并独立重放动作。

```bash
python -m unittest discover -s question4/tests -v
```

16项测试覆盖方向边界、近场、光学背面清除、误差极值、连续覆盖证书、篡改、幂等重试、状态不确定与本机HTTP默认推荐入口。本机HTTP测试需要允许监听loopback临时端口。

## 论文证据

- `results/experiment_index.json`：15批实验数量、阶段和完整性索引。
- `results/round9_review.json`：最终均值、P95、配对bootstrap区间、分组与最差案例。
- `results/final_review.json`：上一阶段22站预选方案的消融反转；属于历史结果，非最终推荐。
- 每批 `lock.json`、`fixtures.json`、`code_snapshot/`、`summary.json`、`comparison.json`：独立验证与复现材料。
- 每个配置／案例目录下 `actions.jsonl`、`strategy.jsonl`、`result.json`：原始动作及运行后审计证据。
- `results/negative21_counterexample.json`：21站方案漏检的几何反例。
- `figures/`：用于论文的SVG和PNG图。
- `releases/`：推荐运行包、完整实验归档及SHA256；大压缩包和逐案例日志仅保留本地。

运行模块复用 `question3/interface.py` 的HTTP、重试和计时实现；自建HTTP辅助服务复用 `question3/self_server.py`。第三问源码、推荐配置和既有证据未改动。不要只复制 `question4/strategy.py` 单个文件。
