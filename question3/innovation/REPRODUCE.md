# 论文复现与运行入口

以下命令从仓库根目录执行，需要 `question3/requirements.txt` 中的依赖。输出目录必须尚不存在。

## 冻结的原方法与新方法公平对照

```bash
python question3/innovation/validate.py
python question3/innovation/run_self.py --round replays/check_main --variants BASE,GATED_TOUR_MULTI_PARALLAX --fixtures question3/innovation/final_validation_cases.json --stage replay_seen_validation --lock question3/innovation/validation_lock.json --limit 4
```

这里 `--limit 4` 取前四个“布局×误差场”实例，两个方案共八局，供快速检查。删掉 `--limit 4` 即为每方案 480 局的完整有界误差重放。舍入压力重放增加 `--rounding pre_round_stress`，另用 `--round replays/check_stress`。

运行文件时请使用上面的直接文件入口，以确保原方法来自 `frozen`，不要改成 `python -m question3.innovation.run_self`。所有原始动作、策略日志、评估器结果会在 `question3/innovation/replays` 下重新生成，该目录被 Git 忽略。原始已见验证布局的重放不是新留出验证；不能用它调参后仍声称独立验证。

如需单独运行旧方法，保留 `--variants BASE` 即可。复跑最终八臂消融时，使用锁中的八个方案名，用逗号分隔传给 `--variants`；配置由原验证锁校验。历史批次复现应使用该批 `code_snapshot` 和 `configs.json`，不能用最终源码替代早期机制版本。

`analyze_final.py`、`deliver.py` 是原探索阶段的分析和报告生成源码，保留用于审查；后者还需要 Matplotlib 和原逐动作日志来绘制路径，并会重写历史报告，只应在临时副本中运行。现有表格、逐例指标和图已经归档，可直接用于论文。完整导出检查可运行 `python question3/diagnostics/verify_mechanism_export.py`，其中 HTTP 测试只使用本机临时端口。首次受沙箱限制无法创建 socket 的记录保留在 `EXPORT_VERIFICATION_sandbox.log`，成功重试见 `EXPORT_VERIFICATION.log`；前者属于测试基础设施失败。

## 自建 HTTP：分别运行原方法与新方法

在另一个终端先启动一次自建服务：

```bash
python -m question3.self_server --port 2027 --seed 0
```

原方法：

```bash
python -m question3.run_http --mode self-http --config question3/configs/recommended_omni.json --output question3/results/replay_original_http
```

重启相同 seed 的自建服务，让环境恢复到相同初始状态，再运行新方法：

```bash
python -m question3.run_innovation_http --mode self-http --output question3/results/replay_innovation_http
```

新入口固定使用已锁定的 `innovation/best_candidate.json`，保存配置、源码摘要、动作、策略事件与结果。两个入口共用仓库现有 `question3/interface.py` 的请求字段、重试、返回值解析和计时。

## 之后人工启动的官方演练

本次提交没有启动官方程序。以后由操作者按[现有演练说明](../演练测试使用说明.md)准备好第三问演练界面后，分别使用独立新场景运行，不能在已经清除的同一局依次调用两种算法：

```text
python -m question3.run_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --config question3/configs/recommended_omni.json --output question3/results/original_rehearsal_001
python -m question3.run_innovation_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --output question3/results/innovation_rehearsal_001
```

保持当前云端官方协议与默认端口 2026，不提供正式测试模式，也不启动或操作模拟器界面。以上是将来可用的命令，不代表本次已完成官方或 Windows 验证。若官方场景不能精确重放，论文须将非配对官方结果与配对自建结果分开报告。
