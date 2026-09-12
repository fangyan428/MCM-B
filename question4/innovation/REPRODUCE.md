# 复现本轮第四问机制实验

所有下列命令只使用自建 `Simulator`，不连接官方HTTP、不启动官方程序、不推送云端。原25站推荐仍在 `question4/configs/recommended.json`，本轮候选在 `best_candidate.json`。

## 运行环境

算法批次记录的Python/NumPy/SciPy版本见各批summary.json的environment。本轮算法使用Python 3.13、NumPy 2.4.4、SciPy 1.17.1。建议在独立环境安装依赖，避免修改其他项目的环境：

```bash
python -m pip install -r question4/requirements.txt
```

绘图是运行后独立步骤，另需 `reporting/requirements.txt`；它不是策略依赖，也不计入虚拟时间。为兼容项目实际环境，报告生成器只使用常规Matplotlib与NumPy接口。

## 复现最终矩阵

在项目根目录，用新输出目录运行；已有目录会被拒绝，不能覆盖证据：

```bash
python -m question4.innovation.experiment \
  --configs question4/innovation/configs/final.json \
  --selection question4/innovation/FINAL_SELECTION.md \
  --fixtures question4/innovation/results/final_validation/fixtures.json \
  --lock question4/innovation/results/final_validation/lock.json \
  --output question4/innovation/results/final_reproduction \
  --error-modes spatial_hash,positive,negative,smooth \
  --roundings bounded,pre_round_stress \
  --workers 4 --stage reproduction_not_independent
```

`--fixtures` 先按真实布局去重，再按参数完整交叉，因此必须显式写误差和舍入轴。复用旧布局仅叫复现，不叫新独立验证。request_id和实际时间戳每次不同，比较虚拟时间、动作位置/频道/结果及计时分量，不要求UUID或壁钟时间逐字一致。

如果工作区源码已更新，进入该批 `code_snapshot/` 作为根目录再运行；所有配置、fixture、lock、selection路径改用批次目录的绝对路径。恢复到独立目录，不要覆盖当前源码或修改旧锁。

```bash
python -m question4.innovation.analysis \
  --input question4/innovation/results/final_reproduction \
  --output question4/innovation/results/final_reproduction/statistics.json \
  --bootstrap 10000
```

分析器先核验完整配置×场景矩阵、源码快照与integrity，再报告均值、P95、最大值、布局分层bootstrap和最差配对案例。不完整或框架中断批次不能作为正常成绩；策略/审计失败保留，按max(实际时间,360000秒)惩罚。

## 复现早期批次

`round01_dev` 与 `round02_dev` 均为24个相同开发布局、`spatial_hash,positive`、`bounded`；后者为显式复用。`round01_validation`、`round02_validation` 分别48个新布局，均四误差×两舍入。使用对应批次源码快照与显式交叉轴。R1源码在R2做过框架完整性修复，不能用当前源去冒充旧锁；R1选择锁的元数据补充见 `locks/round01/PROVENANCE.md`。

新独立验证应先用 `python -m question4.innovation.lock --help` 创建绑定选择决策、源码、配置、父证据与新设计的锁，再运行experiment的 `--seed/--count/--lock`；种子和生成布局必须与此前所有批次分离。读取新结果后改变候选，就需要下一批新验证，不能回填旧验证结论。

## 自建边界测试与报告

```bash
python -m unittest question4.innovation.test_mechanisms \
  question4.tests.test_contract question4.tests.test_faults -v
PYTHONPATH=. python question4/innovation/reporting/finalize.py --candidate ADAPT_GATED
PYTHONPATH=. python question4/innovation/reporting/replay.py
```

报告脚本应在项目根目录运行并设置 `PYTHONPATH=.`（或通过已安装的项目路径导入），仅读取已经结束的实验。最终统计、宽表、停止证据和图由该脚本重建。测试覆盖定向背面近场、接收边界、极端方位误差、集合与清除证书、影区跳过证书、协议故障；不包含官方测试或Windows实测。

每批原始 `actions.jsonl`、`strategy.jsonl`、`result.json`、评估器布局、锁和快照保留本地。布局真值只在评估器和运行后审计/绘图中读取；不作为策略输入。
