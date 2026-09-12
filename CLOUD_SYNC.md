# 云端代码与本地实验留档

云端保存第一至四问代码、配置、测试、建模报告，以及第三、四问各轮协议、汇总、配对结果、场景fixture、代码锁和历史源码快照。第三问当前推荐为 `question3/configs/recommended_omni.json`；第四问当前推荐为 `question4/configs/recommended.json`。

以下新增产物只保留本地，不上传Git：

- `paper_evidence/`（同时忽略`paper-evidence/`拼写）：默认只保留本地；第四问机制重新探索目录是明确的白名单例外，详见下文。
- 第三问逐案例的`actions.jsonl`、`strategy.jsonl`、`result.json`和`evaluator_hidden_case.json`。
- `question3/releases/*.zip`运行压缩包；其发布清单与SHA256仍可提交。

这些规则不会删除本地资料，也不会移除历史提交中已经跟踪的旧文件。完整原始证据已在本地`paper_evidence/完整实验原始记录.tar.gz`归档并逐文件校验；仅克隆Git仓库不能视为已获得全部实验原始日志。

克隆仓库后可直接在项目根目录安装依赖并运行代码，无需运行压缩包：

```text
python -m pip install -r question3/requirements.txt
```

自建运行和Windows官方演练操作见 `question3/RUN_RECOMMENDED.md`。其中“解压运行包”的准备步骤可替换为克隆仓库；正式测试仍需明确授权。第四问的官方演练和正式测试尚未执行，第四问云端汇总仍是自建实验结果。第三问后续演练状态以其最新操作说明及记录为准。

复核已有逐案例审计需要本地原始归档，或使用对应源码快照、配置、fixture及新输出目录重新运行。不要将重放旧数据称为新的独立验证，也不要用最终源码冒充早期锁定源码。

## 第四问增补

第四问交付位于 `question4/`，推荐配置为 `question4/configs/recommended.json`，操作和证据索引见 `question4/README.md`。源码、配置、证明、各轮汇总、fixture、锁和代码快照可随Git保存；第四问逐案例动作日志、策略日志、结果原件及 `releases/` 中的大压缩包只保留本地，其索引和SHA256可提交。

第四问历史完整证据另存于本地 `question4/releases/q4_experiment_evidence.tar.gz`；追加实验位于 `question4/innovation/`，其逐案例日志及大压缩包同样留在本地。源码、报告、汇总、场景和锁文件上传。

2026-09-12 用户确认保留原25站推荐，并授权将第四问代码等推送云端。十轮机制重新探索位于 `paper_evidence/q4_mechanism_reset_20260912/`：该目录的源码、配置、逐轮结论、汇总、fixture、冻结源码快照及SHA256清单列入Git；逐案例 `actions.jsonl`、`strategy.jsonl`、`result.json`、`evaluator_hidden_case.json`、运行zip及冻结题面附件副本仍只保留本地。其他 `paper_evidence/` 目录继续忽略。

本地 `ARTIFACT_SHA256.json` 对完整原始材料建立清单，其中包含未上传文件；它不表示克隆仓库已包含所有原始日志。历史“未推送”记录描述当时状态，本次明确授权的Git同步不改变已冻结实验结论。没有执行官方演练或正式测试。
