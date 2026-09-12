# 复现说明

在项目根目录运行。实验环境记录于每批 summary.json：Python 3.13.12、NumPy 2.4.4、SciPy 1.17.1。不要用 `python -O`，物理审计包含断言。所有命令仅使用进程内自建Simulator，不连接HTTP或官方模拟器。

## 重放已有最终场景

使用全新输出目录，保留原始记录。复用场景属于复现，不能称为新的独立验证。

```bash
python -m paper_evidence.q4_mechanism_reset_20260912.experiment \
  --configs paper_evidence/q4_mechanism_reset_20260912/candidate_matrix.json \
  --output paper_evidence/q4_mechanism_reset_20260912/reproduce_final_001 \
  --fixtures paper_evidence/q4_mechanism_reset_20260912/final_validation/fixtures.json \
  --error-modes spatial_hash,positive,negative,smooth \
  --roundings bounded,pre_round_stress --workers 4 \
  --stage reproduction_not_new_validation --reference BASE25 \
  --lock paper_evidence/q4_mechanism_reset_20260912/validation_lock/lock.json
```

若工作树代码已变，先把 `final_validation/code_snapshot/` 中的项目相对路径内容恢复到一个独立副本，再运行；不要改锁文件或覆盖当前推荐。

## 逐轮开发复现

每轮 `command.json` 保存真实命令，`execution.log` 保存完整标准输出。把其中 `--output` 改为新的目录即可重放同样seed 291000起24布局。每轮配置预算是一个预设核心方案，已有组合/消融另列，没有外部参数扫描。修正实现、图表环境问题和审计测试与性能结果分开保存。

## 无隐藏真值的公共响应重放

`qa/replay.py` 只消费单案例 actions.jsonl 公共请求/响应，不需要evaluator_hidden_case.json。读取 [公共重放说明](qa/REPLAY.md)。已有6条最终基线/候选公共轨迹精确重放记录在 `qa/final_replay_summary.json`。

## 证据与边界

`freeze_manifest.json`冻结原推荐和原题；每批 lock.json/metadata.json/snapshot_complete.json 证明先锁代码再造数据；`integrity.json`验证运行期间代码未变。`PROVENANCE_CHECK.json`检查最终物理布局与旧第四问、开发、对抗场景不重叠。

策略只有position、channel、enter、measure、clear、exit、metrics。真值只供环境返回响应及运行后的独立审计。每局 result.json保留清除总数、错误、超时标记、原始/惩罚时间与审计结论；失败不会被筛掉。

最终表由 `python -m paper_evidence.q4_mechanism_reset_20260912.reporting.finalize` 从原始summary生成；它固定候选名，不做事后选优。最终bootstrap按布局分块、六家族分层，不把8种误差/舍入组合当独立样本。
