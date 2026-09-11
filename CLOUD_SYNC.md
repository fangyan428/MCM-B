# 云端代码与本地实验留档

云端保存第一、二、三问代码、配置、测试、建模报告，以及第三问各轮协议、汇总、配对结果、场景fixture、代码锁和历史源码快照。当前推荐配置为 `question3/configs/recommended_omni.json`。

以下新增产物只保留本地，不上传Git：

- `paper_evidence/`（同时忽略`paper-evidence/`拼写）：论文写作索引、查阅副本与完整实验压缩包。
- 第三问逐案例的`actions.jsonl`、`strategy.jsonl`、`result.json`和`evaluator_hidden_case.json`。
- `question3/releases/*.zip`运行压缩包；其发布清单与SHA256仍可提交。

这些规则不会删除本地资料，也不会移除历史提交中已经跟踪的旧文件。完整原始证据已在本地`paper_evidence/完整实验原始记录.tar.gz`归档并逐文件校验；仅克隆Git仓库不能视为已获得全部实验原始日志。

克隆仓库后可直接在项目根目录安装依赖并运行代码，无需运行压缩包：

```text
python -m pip install -r question3/requirements.txt
```

自建运行和Windows官方演练操作见 `question3/RUN_RECOMMENDED.md`。其中“解压运行包”的准备步骤可替换为克隆仓库；正式测试仍需明确授权。官方演练和正式测试尚未执行，云端汇总仍是自建实验结果。

复核已有逐案例审计需要本地原始归档，或使用对应源码快照、配置、fixture及新输出目录重新运行。不要将重放旧数据称为新的独立验证，也不要用最终源码冒充早期锁定源码。
