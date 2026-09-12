# 第三方公共响应重放

`replay.py` 只读取单案例的 `actions.jsonl` 和用于结束后比较的 `result.json`，不读取 `evaluator_hidden_case.json`、fixtures、源位置、源方向或误差场。策略接口仅含 `position`、`channel`、`enter/measure/clear/exit` 与 `metrics`；不暴露 `transport`、`Simulator`、`hidden`、`case`、`truth` 或 `evaluation` 属性。

录制传输器严格顺序匹配下一条公开请求：路径、全部坐标、频道、robot/arena字段须完全一致，才返回相应的录制响应。唯一允许变化的是新进程的 `request_id`，并验证同ID重试和新动作ID隔离。时间戳保持录制值；策略不使用它决定动作。若日志有运输错误，它以 `OSError` 重放，使原客户端执行同ID重试。

用单配置或配置矩阵均可：

```bash
python -m paper_evidence.q4_mechanism_reset_20260912.qa.replay \
  --case-dir paper_evidence/q4_mechanism_reset_20260912/round01_action_tasks/development/BASE25/uniform_e5ca39cddadc51f1__smooth__bounded \
  --config '{"family":"baseline"}' \
  --output paper_evidence/q4_mechanism_reset_20260912/qa/new_replay_base

python -m paper_evidence.q4_mechanism_reset_20260912.qa.replay \
  --case-dir <实验批次>/<候选名>/<案例ID> \
  --config <配置矩阵.json> --config-name <候选名> \
  --output <不存在的新输出目录>
```

输出目录不得已存在，也不得在输入单案例目录内部。每次重放保存新的动作、策略事件、结果、`replay.json` 与 `static_scan.json`；不会覆盖原记录。错误也保存已产生动作及失败报告，并以非零退出码结束。

通过要求同时满足：

- 全部录制动作被消费，未多发、少发或改变任何坐标/频道。
- 完成状态及已清除频道列表相同。
- 总时间、组件、阶段与计数的完整 `metrics` 精确相同。
- 停止证书与逐请求阶段归属相同。
- 递归策略依赖AST扫描未发现禁止访问。

静态扫描从本轮策略dispatcher开始，解析仓库内相对/绝对Python依赖，保存文件SHA256与imports。禁止源案例、仿真器、实验器、HTTP运行入口等导入，以及典型隐藏字段/字典键访问；动态反射和文件读取单列为人工复核项，不静默放行。本轮检查到13个本地策略模块、0项禁止访问；6项人工复核均来自原版及冻结版 `geometry.py` 的公开 `compact22.json` 覆盖证书读取/JSON解码。这个文件只包含固定几何证书，没有场景真值；本轮基线和新候选使用radial/dynamic覆盖，通常不会执行compact分支。

`test_replay.py` 的5项测试覆盖坐标微改拒绝、日志后多发拒绝、请求ID重映射与重试一致性、禁止导入/隐藏字段检出、当前代码依赖检查。记录见 `test_replay.log`。`replay_smoke_base/` 已重放一个基线开发案例，355条接受动作、位置/频道/metrics/证书全部一致。

证据局限：这说明选定记录在没有仿真器/真值输入时可由相同公开响应逐动作重现，不是对所有可能响应或恶意Python反射的形式化安全证明。AST分析不覆盖外部库内部，也不构成沙箱。策略代码的SHA256应与待复核实验的锁一致；科学复现还需要保留同Python/NumPy/SciPy版本和浮点环境。
