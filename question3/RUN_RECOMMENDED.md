# 第三问推荐版：运行与结果核对

完整的 Windows 官方模拟器演练流程、最终配置核对、统计登记表和故障处理见：[演练测试使用说明](演练测试使用说明.md)。

当前配置`question3/configs/recommended_omni.json`为第十九轮BOTH：第十六轮FREE加上主目标和共享目标各自的公开区域距离证书。接收、交角、光学覆盖、完整清除和可靠停止仍有相应条件与审计。

2824局自建矩阵全部完整清除，162项测试通过。70个新布局中普通均值降低6.11%/6.37%、外缘降低7.30%/6.70%，四批P95均下降；最差新单例变慢10.75%。按用户指示在此结束自主优化，未声称全局最优。Windows/官方模拟器尚未实测，正式测试仍需明确授权。

旧第十六轮`configs/round16_dev/FREE.json`和原包、AB均保留；第十七轮静态扫描路线关闭。严格复现旧源码锁应使用对应原包，不能用当前源码替代旧版。

## 文件准备

解压`q3_omni_round19.zip`，保留同级question1、question2、question3。在包含三个目录的项目根目录打开终端：

```text
python -m pip install -r question3/requirements.txt
```

开发环境与版本在发布清单和实验summary中。使用跨平台Python接口，不需要Wine。旧第七轮K在`configs/round7_k_holdout/K.json`，原AB在`configs/round1/AB.json`。

## 自建HTTP回归

第一个终端：

```text
python -m question3.self_server --port 2027 --seed 0
```

第二个终端：

```text
python -m question3.run_http --mode self-http --url http://127.0.0.1:2027 --config question3/configs/recommended_omni.json --output question3/results/self_recommended_001
```

这是自建测试。每次使用新输出目录，保留日志，不覆盖旧结果。

## Windows官方第三问演练

在Windows启动给定官方exe并登录，手工选择第三问全向源的**演练测试**，等待倒计时结束和接口就绪。在同一电脑、项目根目录运行，替换队号：

```text
python -m question3.run_http --mode official-rehearsal --confirm-rehearsal-ui --robot-id YOUR_TEAM_ID --config question3/configs/recommended_omni.json --output question3/results/windows_recommended_001
```

默认127.0.0.1:2026。确认参数表示操作者已检查当前界面是演练；HTTP不能识别是否误选正式模式。代码不启动exe、不操作界面。本轮未执行官方命令，正式测试仍需用户明确授权。

## 检测与停止证书

主目标及共享频道分别用自己的首次方位和题面区域边界计算距离上界；仅在相应整个误差区域满足接收、交角条件时使用该第二点。只有当前位置通过这些条件才原地做第二检测；每次仍收取检测与必要切频费。先选目标再检查原地机会，已缓存目标不重复检测。不会用同点重复测量平均误差。

题面最多16源且频道互异。发现16个不同频道后可结束未知频道搜索，但必须继续清除所有已知源。只有16个不同频道收到有效成功清除反馈，才能以`source_count_upper_bound`证书完成；不足16时仍要求原逐频道七站证书`seven_station_channel_cover`。发现10个、连续无信号或仅发现16个但未清除，都不能直接报完成。

数量证书的其余频道由上限推断无源，不能写成“七站检测均无信号”。接口未提供的实际总数仍保留null，推断单列于证书，不伪装成接口返回值。

结果目录保存实际配置、actions.jsonl、strategy.jsonl和result.json。记录官方案例编码、界面总数/清除数/总虚拟时间，与日志核对。异常时保留日志，不在同一局盲目重启脚本。

## 当前证据与保留版本

第十九轮报告`docs/第十九轮区域共享组合与收敛交付.md`；锁`results/round19_lock.json`；全部对照、交互及回归`results/round19_review_evidence.json`。精简包附源码、协议、配置、fixtures、汇总及代表日志，完整逐动作矩阵在工作区results。提取包独立自建检查见`results/round19_release_package_smoke.json`（工作区交付旁证），包哈希见`.zip.sha256`。

本轮仍有回归：新外缘2103.98→2330.16秒，约10.75%；新普通最差约1.03%。切回旧版可更换显式配置路径；严格复现旧源码锁用对应原包。官方结果仍待实际演练，严禁把自建成绩填成官方成绩。
