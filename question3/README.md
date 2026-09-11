# 全向源第三问基线（当前停在人工审查节点）

入口文稿：[基线建模、证据与三个创新候选](docs/基线建模与审查.md)。第二问复核：[复核补充](../question2/第二问_复核补充.md)。

当前只实现baseline_v1；创新候选尚未获批、未实施。官方演练0次，正式测试0次；未运行项目中的exe。

## 文件分工

| 文件 | 职责 |
|---|---|
| strategy.py | 搜索、定位、清除、停止证书；不读取真值 |
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
python -m question3.run_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --output question3/results/windows_rehearsal_001
```

4. 同一电脑连接127.0.0.1:2026；如官方端口改动，传`--url`。不要让Ubuntu和Windows同时登录同一官方账号。
5. 结束后手工保存官方演练案例编码、界面给出的总数、清除数、虚拟时间及运行时间；与自有日志核对。客户端将官方总数和清除比例保留为null，不伪造接口未提供的真值。正式日志格式和大小必须在官方环境另查。

`--confirm-rehearsal-ui`是操作者确认，不是对官方模式的技术鉴别。代码没有正式测试模式，也不会点击任何启动按钮。未经用户另行明确批准，不得启动正式测试。

本轮提供上述接入流程及接口代码，但未执行Windows或官方演练。自建通过不等于官方通过；若官方accepted状态、误差包络或计时出现矛盾，保留原始日志并暂停审查。

## 限制与可追溯性

JSONL保存每次请求、响应、重试；strategy日志保存覆盖检查及定位区域。每局result包含停止证书和计时分解，summary包含代码SHA256与环境信息。独立审计在策略结束后核对真值；不会在运行中修正策略。

故障后的incomplete可能意味着部分源已经清除，但系统没有足够证据确认完整成功。不要手工将其改为complete，也不要把无返回值的正式接口动作随意用新ID重发。
