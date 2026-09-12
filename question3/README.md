# 全向源第三问：自主优化推荐版与验证记录

当前交付推荐为`configs/recommended_omni.json`（第十九轮BOTH：第十六轮FREE加主目标及共享目标的公开区域距离证书）。2824局自建对照全部完整清除，162项测试通过；70个新布局中普通均值降低6.11%/6.37%，外缘降低7.30%/6.70%，四批P95均下降。最差新单例仍变慢10.75%，不宣称全局最优。按用户指示在此收敛，不再继续调参。见[最终交付报告及失败案例](docs/第十九轮区域共享组合与收敛交付.md)、[运行说明](RUN_RECOMMENDED.md)。第十九轮源码包、旧第十六轮及AB均保留；官方程序未运行。

Windows 官方模拟器的最终方案演练步骤、命令、验收条件、统计登记表和故障处理见[演练测试使用说明](演练测试使用说明.md)。

第十八轮区域先验主目标版本1400局全部完整清除、156项测试通过；新普通均值约降5.3%，但新外缘均值上升约6%，未采纳。已定位到与共享资格证书不一致的冲突，见[新验证与下一轮单项/组合方向](docs/第十八轮区域距离证书与共享冲突.md)。推荐配置及原包不变。

第十七轮完整扫描路径276局全部完整清除、149项测试通过，但两误差开发均值和P95均上升，不采纳，推荐包不变。见[负结果与下一项合法区域先验](docs/第十七轮扫描路径负结果与区域先验机会.md)。根源码含默认关闭的新模块，严格复现第十六轮锁应使用原包。

第十四轮相位调整开发改善，但新普通均值和P95均变差，最差个体+27.96%，因此不采纳。实际1584局矩阵（含208局保留复跑）全部完整清除，最终131项测试通过；推荐包不变。见[独立验证失败与下一项机制](docs/第十四轮外环相位独立验证失败.md)。

第十五轮定位批次402局全部完整清除，138项测试通过；缓存优先均值改善但舍入P95略升，已知优先尾部改善但舍入均值上升，均未采纳。见[最新取舍与后续简化方向](docs/第十五轮定位批次调度取舍.md)。

第十二轮组合半平面候选256局全部完整清除，但没有新增耗时收益，推荐及第十一轮运行包不变；当前源码115项测试通过。见[第十二轮负结果与下一项机会](docs/第十二轮组合半平面分离负结果.md)。

第八轮已验证当前位置检测J/Z，预选Z未通过外缘舍入均值门槛，推荐保持第七轮K；见[第八轮结果](docs/第八轮当前位置检测与调度耦合.md)。

第六轮已验证缓存插入排序、光学路径反向及其组合，未通过预设采纳门槛，当前推荐不变；见[负结果与继续方向](docs/第六轮缓存排序与覆盖遍历负结果.md)。

入口文稿：[基线建模、证据与三个创新候选](docs/基线建模与审查.md)。第二问复核：[复核补充](../question2/第二问_复核补充.md)。

当前实现baseline_v1、A/B/C三个可配置模块及第二轮前瞻消融。第一轮八种组合见[第一轮结果与审查](docs/第一轮模块对照与审查.md)；第二轮开发与锁参后的新布局验证见[第二轮审查](docs/第二轮前瞻消融与新案例审查.md)；最新单项及组合结果见[第三轮审查](docs/第三轮单项与组合实验审查.md)。以[STATUS](STATUS.md)为当前节点，旧报告保留阶段历史。官方演练0次，正式测试0次；未运行项目中的exe。

## 文件分工

| 文件 | 职责 |
|---|---|
| strategy.py | 搜索、定位、清除、停止证书；不读取真值 |
| modules.py | A局部代价选点与C合法证据覆盖；B在公共策略调度循环 |
| lookahead.py | 第二轮可选调度：数值平局、任务成本、终点区域一步前瞻 |
| geometry.py | 七站覆盖、第二点证书、复用第一问求交、光学网格 |
| interface.py | HTTP、幂等重试、接受状态、计时、JSONL日志 |
| simulator.py / cases.py | 自建全向环境及隐藏案例；策略不导入 |
| self_server.py | 仅本机自建HTTP服务，默认2027端口 |
| run_self.py | 自建开发运行；结束后由评估器核对隐藏真值 |
| run_http.py | 同一策略连接自建HTTP或已就绪的官方第三问演练 |
| audit.py | 运行后的独立日志/物理/停止证书审计 |
| run_faults.py | 故障注入日志，不能混入合法案例成绩 |
| configs/baseline.json | 固定基线参数；不随案例真值调整 |
| configs/proposed_experiments.json | 尚未执行的创新实验与新案例计划 |
| results/baseline_v1 | 最终主自建运行、每局完整日志、评估真值、汇总及审计 |
| results/rounding_v1 | 单独标识的舍入压力实验 |
| results/verification.txt | 实际测试命令与输出 |

`evaluator_hidden_case.json`只供评估与复现，不得传给策略或用于行动决策。开发结果使用同批布局的多种误差场，不是留出测试结果。此前smoke、baseline_dev、rounding_stress目录保留为开发轨迹。

## 复现第一轮八种配置

在项目根目录运行，输出目录必须是新的，避免覆盖已有结果：

```bash
python -m question3.run_matrix --output question3/results/my_round1_main
python -m question3.analyze_matrix question3/results/my_round1_main
python -m question3.run_matrix --output question3/results/my_round1_rounding --rounding pre_round_stress
python -m question3.analyze_matrix question3/results/my_round1_rounding
```

八份配置位于`configs/round1/`，每个配置仅用一套固定参数。上述命令只使用已有development_cases；留出案例必须通过配置锁和独立生成器。两个结果目录均包含每例原始JSONL、评估结果、运行时代码快照、完整对照JSON及配对CSV。A/B/C全关闭时与旧基线52例metrics完全一致。

模块名称及收益限于第一轮结论；旧`configs/proposed_experiments.json`为上一审查阶段的历史提案，当前以`docs/round1_protocol.json`和第一轮报告为准。`run_http.py`默认仍为基线；用户已选保留AB，运行AB必须显式传`--config question3/configs/round1/AB.json`。该入口补丁不改变策略。

## 复现第二轮（自建环境）

第二轮开发配置在`configs/round2/`。代码和四份验证配置在生成新布局前锁定，锁文件为`results/round2_lock.json`；随后才生成`results/round2_holdout_cases.json`。不要在看过验证结果后改配置并把重跑称为新验证。

```bash
python -m question3.run_matrix --config-dir question3/configs/round2 --stage SELF_ROUND2_DEVELOPMENT --output question3/results/my_round2_dev
python -m question3.analyze_matrix question3/results/my_round2_dev --reference AB
python -m question3.run_matrix --config-dir question3/configs/round2_holdout --fixtures question3/results/round2_holdout_cases.json --lock question3/results/round2_lock.json --stage SELF_ROUND2_HELDOUT --output question3/results/my_round2_holdout
python -m question3.analyze_matrix question3/results/my_round2_holdout --reference AB
```

舍入压力批次使用同样命令，增加`--rounding pre_round_stress`并使用新输出目录和明确的压力阶段名。已有完整结果位于`results/round2_dev`、`round2_dev_rounding`、`round2_holdout_main`、`round2_holdout_rounding`。每个目录保存配置、逐例动作、策略决策、评估真值、汇总、配对表及代码快照。未来代码发生变化后，应在独立目录恢复该批`code_snapshot`中的文件再复现，以免违反代码锁。

## Ubuntu自建开发

在项目根目录，用已有Python环境安装依赖（如尚未安装）：

```bash
python -m pip install -r question3/requirements.txt
python -m question3.run_self --output question3/results/my_self_run
python -m question3.audit question3/results/my_self_run
python -m unittest discover -s question3/tests -v
```

请给新运行使用新目录名。配置按题面固定，当前实现不提供在线调参。实测开发环境为Ubuntu、Python3.13.12、NumPy2.4.4、SciPy1.17.1；Windows运行尚未实测，代码采用跨平台路径、Python标准HTTP库及NumPy/SciPy。

真实本机HTTP验证可用两个终端：

```bash
python -m question3.self_server --port 2027 --seed 0
```

```bash
python -m question3.run_http --mode self-http --url http://127.0.0.1:2027 --output question3/results/my_self_http
```

该服务仅绑定127.0.0.1，不访问官方网络；种子参数只在环境端使用。动作完成不需现实等待5秒，5秒是虚拟时间。

## 之后转Windows官方演练

建议保留Ubuntu自建环境用于快速回归，随后在Windows用给定exe开展官方**问题3演练测试**。项目中exe被识别为Windows x86-64 GUI程序，未在Ubuntu执行或尝试登录。

1. 把包含question1、question2、question3的整个项目复制到Windows；安装Python依赖。两端运行入口相同，不需改变策略代码。
2. 在Windows启动官方模拟器、登录账号，手工选择**问题3演练测试**，等待界面显示接口就绪。不要选择正式测试；程序不能通过四个API识别界面当前模式。
3. 在项目根目录终端执行下列演练命令，将队号替换为真实robot_id：

```text
python -m question3.run_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --config question3/configs/round1/AB.json --output question3/results/windows_rehearsal_001
```

4. 同一电脑连接127.0.0.1:2026；如官方端口改动，传`--url`。不要让Ubuntu和Windows同时登录同一官方账号。
5. 结束后手工保存官方演练案例编码、界面给出的总数、清除数、虚拟时间及运行时间；与自有日志核对。客户端将官方总数和清除比例保留为null，不伪造接口未提供的真值。正式日志格式和大小必须在官方环境另查。

`--confirm-rehearsal-ui`是操作者确认，不是对官方模式的技术鉴别。代码没有正式测试模式，也不会点击任何启动按钮。未经用户另行明确批准，不得启动正式测试。

本轮提供上述接入流程及接口代码，但未执行Windows或官方演练。自建通过不等于官方通过；若官方accepted状态、误差包络或计时出现矛盾，保留原始日志并暂停审查。

## 限制与可追溯性

JSONL保存每次请求、响应、重试；strategy日志保存覆盖检查及定位区域。每局result包含停止证书和计时分解，summary包含代码SHA256与环境信息。独立审计在策略结束后核对真值；不会在运行中修正策略。

故障后的incomplete可能意味着部分源已经清除，但系统没有足够证据确认完整成功。不要手工将其改为complete，也不要把无返回值的正式接口动作随意用新ID重发。

## AB演练入口补充

用户已选择保留AB并准备Windows官方演练。HTTP入口新增`--config`，把实际配置另存为输出目录的`config.json`。未指定仍运行旧基线。两项CLI检查已在Ubuntu通过，包括AB经真实本机HTTP完整清除及演练未确认时拒绝运行；Windows与官方服务尚未实测。

该补丁发生在第二轮验证结束后，只修改HTTP启动入口；历史`round2_lock.json`不重写，历史验证结果仍对应各批代码快照。由于锁也包含run_http.py，若现在直接重跑旧锁会报告该文件哈希变化；请恢复历史code_snapshot到独立目录复现。

## 后续优化开发探针

见[第三轮优化机会与开发探针](docs/第三轮优化机会与开发探针.md)。新增可选D单圆覆盖证书只在`configs/round3_probe/ABD.json`启用；官方演练继续显式使用`configs/round1/AB.json`。AB参数未改，其两批52例metrics与历史AB一致。共用检测点的30.30%是当时既有日志的几何机会率，不是预计节省比例；后续实际策略性能见第三轮全因子报告。

## 第三轮三个方向的全因子开发对照

S=共享第二检测点并缓存待清除区域，O=同一站点与源任务的顺序比较，D=单圆清除证书。新代码分别在`shared_measurement.py`、`order_routing.py`、`optical_shortcut.py`，策略默认不启用S/O/D。官方演练仍用原`configs/round1/AB.json`，不要只复制一个策略文件，应复制整个question3目录。

八份配置在`configs/round3_factorial/`，全部单项及兼容组合已在同52个开发案例上测试。完整主环境/压力结果在`results/round3_factorial_main/`与`results/round3_factorial_rounding/`，明确不是新验收集。见[第三轮报告](docs/第三轮单项与组合实验审查.md)。

```bash
python -m question3.run_matrix --config-dir question3/configs/round3_factorial --stage SELF_ROUND3_DEVELOPMENT_FACTORIAL_NOT_HELDOUT --output question3/results/my_round3
python -m question3.analyze_matrix question3/results/my_round3 --reference AB
python -m question3.diagnostics.factorial_review question3/results/my_round3
```

压力实验增加`--rounding pre_round_stress`并使用另一新目录。故障日志单独保存在`results/round3_factorial_faults/`，不能混入合法案例成绩。当前S/O只支持B的nearest调度，不支持与旧H评分混搭；新三模块的所有8种组合均兼容并已运行。代码快照及哈希一致性见`results/round3_factorial_provenance.json`。

## 本轮推荐配置

运行推荐版时，现有HTTP命令增加或替换为`--config question3/configs/recommended_omni.json`。原AB仍保留作回归对照，默认入口未暗中改配置。代码及参数在新布局生成前锁定；完整数据目录、SHA256、消融和所有负面案例见最新报告。本轮自主研发已经完成，不再等待人工审查；官方/正式测试没有自动启动。
