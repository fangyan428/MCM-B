"""Analyze the frozen final matrix; never selects a different candidate."""
import json,hashlib
from pathlib import Path
import numpy as np
from question4.innovation.analysis import analyze,validate_batch
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1]

def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def main():
 summary=json.loads((ROOT/'final_validation/summary.json').read_text())
 valid=validate_batch(ROOT/'final_validation/summary.json',summary)
 report=analyze(summary['rows'],reference='BASE25',bootstrap=10000)
 report['matrix_audit']=valid
 for name,s in report['configurations'].items():
  s['timeouts']=sum(bool(r.get('timeout')) for r in summary['rows'] if r['config']==name)
 write(ROOT/'FINAL_STATISTICS.json',report)
 final_ids={r['layout_sha256'] for r in summary['rows']}
 all_old=set();sets={}
 for p in list((PROJECT/'question4/results').glob('*/fixtures.json'))+list((PROJECT/'question4/innovation/results').glob('*/fixtures.json'))+list(ROOT.glob('round*/development/fixtures.json'))+[ROOT/'stress/results/fixtures.json']:
  cases=json.loads(p.read_text())
  ids={hashlib.sha256(json.dumps(sorted(c['sources'],key=lambda s:s['channel']),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest() for c in cases}
  sets[str(p.relative_to(PROJECT))]=len(ids&final_ids);all_old|=ids
 assert not all_old&final_ids
 frozen=json.loads((ROOT/'freeze_manifest.json').read_text())
 changed=[p for p,h in frozen['files'].items() if hashlib.sha256((PROJECT/p).read_bytes()).hexdigest()!=h]
 assert not changed
 provenance=dict(final_physical_layouts=len(final_ids),prior_physical_layouts_compared=len(all_old),overlap_by_prior_batch=sets,overlap=0,original_files_changed=changed)
 write(ROOT/'PROVENANCE_CHECK.json',provenance)
 primary='COVER_EXCHANGE_ELASTIC';stats=report['configurations'];base=stats['BASE25'];candidate=stats[primary]
 dev=json.loads((ROOT/'development_evidence.json').read_text());stress=json.loads((ROOT/'stress/results/comparison.json').read_text())
 significant=candidate['gain_ratio_of_means_pct']>=5 and candidate['complete']/candidate['runs']>=base['complete']/base['runs'] and candidate['p95_s']<=base['p95_s']
 evidence=dict(selected=primary,significant_improvement=significant,threshold_gain_pct=5,consecutive_unsuccessful_development_rounds=10,
   final_all_complete_and_audited=all(s['failed']==0 for s in stats.values()),final_algorithm_runs=len(summary['rows']),
   development_algorithm_runs=3168,adversarial_algorithm_runs=640,official_runs=0,source_unchanged=True,
   mean_gain_pct=candidate['gain_ratio_of_means_pct'],p95_gain_pct=(1-candidate['p95_s']/base['p95_s'])*100,
   replace_recommendation=significant,provenance=provenance)
 write(ROOT/'FINAL_EVIDENCE.json',evidence)
 lines=['# 第四问算法机制重新探索：最终报告','',
  f"结论：{'达到预设门槛' if significant else '没有找到满足预设门槛的显著更好方案'}。锁定新候选 {primary} 在最终 120 个未见布局上平均总虚拟时间降低 **{candidate['gain_ratio_of_means_pct']:.3f}%**，P95 {'降低' if candidate['p95_s']<=base['p95_s'] else '增加'} **{abs(evidence['p95_gain_pct']):.3f}%**。建议{'考虑替换' if significant else '保留原 25 站推荐，不为小幅收益增加复杂度'}。",'',
  '共完成 10 个不同核心机制的研发轮次，另有2个组合和1个证书消融。每轮默认预设配置，零外部参数扫描。连续10轮均未达到平均降时≥5%、清除成功率不降低且P95不恶化的联合门槛，小幅收益没有重置计数。按要求停止新机制探索，再对事前选定候选完成独立确认，最终结果没有用于改代码、调参或换候选。','',
  '## 最终完整流程对照','',
  '每臂120布局×4固定误差场×2舍入模型=960局。误差和舍入属于同一布局的重复压力条件，统计单位仍为120个物理布局。表中失败使用 max(实际耗时,360000秒)，原始耗时也在JSON中保留。本次五臂全部成功，因此惩罚与原始时间相同。','',
  '|方案|完整/局数|失败/超时|均值秒|P95秒|最差秒|相对原推荐均值收益|','|---|---:|---:|---:|---:|---:|---:|']
 for name in ['BASE25','HIST_ADAPT','COVER_EXCHANGE','COVER_ELASTIC',primary]:
  s=stats[name];lines.append(f"|{name}|{s['complete']}/{s['runs']}|{s['failed']}/{s['timeouts']}|{s['mean_s']:.2f}|{s['p95_s']:.2f}|{s['max_s']:.2f}|{s['gain_ratio_of_means_pct']:.3f}%|")
 ci=candidate['bootstrap']['gain_ratio_of_means_pct_ci95']
 lines += ['',f"锁定候选均值收益的布局分块、家族分层配对 bootstrap 95%区间为 **[{ci[0]:.3f}%, {ci[1]:.3f}%]**（10000次）。{candidate['wins']}局更快、{candidate['losses']}局更慢、{candidate['ties']}局相同。该区间描述本自建生成器的布局采样变化，不能代表未知官方分布。",'',
  '## 创新机制和消融','',
  '新候选把固定覆盖测站变成可以更新的覆盖见证。成功清除后，若实际到达点可替代一个未访站且全域证书仍成立，就在此处完成该站扫描；访问内环站之前，在保持覆盖边与三角朝向约束下，优化其到当前点及下一个公共任务的局部路线。两种修改都必须重新验证连续覆盖，失败则保留原站。原保守定位与有限光学清除兜底仍执行。','',
  '这区别于调小站距或探测宽度：测站位置由当前已公开动作和任务动态决定，覆盖证书成为每次更新的可行性约束。站点优化使用固定35步计算预算；这是在线算法计算，不是使用测试真值调参。','',
  '最终五臂构成严格2×2消融：BASE25、仅替站、仅移动站、两者组合；HIST_ADAPT是已有历史候选，未作为本次发明。贡献不可简单相加：站点移动会改变接收方向、清除顺序及随后抽到的固定误差场位置。','',
  '|动作组件|原推荐秒/局|锁定候选秒/局|候选−基线|','|---|---:|---:|---:|']
 for k,v in base['components'].items():
  c=candidate['components'].get(k,0);lines.append(f'|{k}|{v:.2f}|{c:.2f}|{c-v:+.2f}|')
 lines += ['','阶段分解（秒/局）：','', '|阶段|原推荐|候选|','|---|---:|---:|']
 for k in sorted(set(base['phases'])|set(candidate['phases'])):
  lines.append(f"|{k}|{base['phases'].get(k,0):.2f}|{candidate['phases'].get(k,0):.2f}|")
 lines += ['','动作组件与阶段是同一总耗时的两种分组，不能相加重复计费。','', '## 十轮结果与放弃原因','', '|轮|机制|开发均值收益|决定|','|---|---|---:|---|']
 for r in dev:
  if r['primary']:lines.append(f"|{r['round'][5:7]}|{r['config']}|{r['gain_ratio_of_means_pct']:.3f}%|未达门槛|")
 lines += ['','动作入口/出口建模未弥补预测误差；固定骨架、两站批处理、全巡视后清除及分区承诺均失去了原在线调度的重要适应性。动态替站触发有限；移动测站获得温和收益，组合仍低于门槛。减少光学单元并不保证早命中更早；清除后额外发现消耗了更多检测和切频；方向阴性位置收缩安全但触发/边际效应很小。每轮详细组件差、最差配对案例、事件频次、配置和原始日志见相应 round*/REVIEW.md 和 development/。','',
  '## 最差案例和可靠性','']
 worst=candidate['worst_paired_cases'][0]
 lines += [f"最差相对案例 `{worst['case_id']}`：原推荐 {worst['baseline_s']:.2f} 秒，候选 {worst['candidate_s']:.2f} 秒，变慢 {worst['regression_s']:.2f} 秒（{abs(worst['gain_pct']):.2f}%）。两者均完整清除。候选最大绝对耗时案例为 `{candidate['worst_case']}`。",'',
 '开发24布局×4误差，10轮合计3168次算法运行；对抗16布局×4误差×2舍入×5臂，640次；最终120新布局×4误差×2舍入×5臂，4800次，合计8608次完整流程自建运行，全部清除并通过逐动作、计时与停止审计。重复基线运行不能计为独立布局；几何单测及历史种子烟测另列，不混入独立验收样本。','',
 '## 对抗复核与证据等级','',
 '- 数学已证明（在所列几何前提下）：直径<1000的三角形包含源时，任意发射半平面至少包含一顶点；四叉树每叶位于近距见证点的凸包内可推广到全连续圆域；有限光学覆盖及16个不同成功清除支持可靠停止。阴性区域收缩的仿射半平面矛盾证明见局部机制审查。',
 '- 实验支持：完整动作费用一致、固定点重复方位一致、最终配对收益及分组结果；公共响应重放和静态依赖复核证明所检查的执行不依赖隐藏布局对象。',
 '- 待验证：未知官方案例分布、官方计时实现、真实网络/Windows环境、所有浮点退化输入的机器级形式证明；本次未执行官方演练或正式测试。',
 '- 旧审计器接受退化伪网格的漏洞已保存反例，本轮增加真实平面Delaunay重建及连续覆盖检查。非入选光学CELL_OPTICAL的独立审计对极薄伪证书有阈值盲点；实际生成器检查通过，仍保留该审计局限，不把全量通过当作形式验证。','',
  '详见 SOURCE_AUDIT.md、qa/LOCAL_ADVERSARIAL.md、qa/FINAL_ADVERSARIAL_REVIEW.md 和 qa/ 公共重放记录。','',
  '## 复现和替换建议','',
  '原推荐、原题附件及已存在的question4源文件哈希全部与freeze_manifest.json一致。只新增paper_evidence本轮目录，没有官方运行、云端推送或替换推荐。复现入口见 REPRODUCE.md；最终代码快照在final_validation/code_snapshot/，锁文件在validation_lock/。','',
  '本轮没有证据支持按5%门槛替换推荐。保留可复现候选作为论文中的约束下自适应覆盖探索与负结果，停止继续叠加机制。']
 lines += ['', '## 终审补充', '',
  '本轮每种新机制采用相同的单配置外部调参预算，但成熟基线已有历史研发投入；不声称各方案累计调参投入完全相同。', '',
  f"本机每局策略计算均值从 {base['wall_mean_s']:.4f} 秒升至 {candidate['wall_mean_s']:.4f} 秒，P95从 {base['wall_p95_s']:.4f} 秒升至 {candidate['wall_p95_s']:.4f} 秒。两者均远低于本机现实期限，但候选引入了更多在线优化计算；这些不是官方网络/Windows实测时间。", '',
  '最差配对案例中，基线完成7站，候选完成19站，均清除16源后按计数停止。候选只触发测站移动，没有触发动态替站；多走的搜索路线涉及11个无新频道发现的站，不能把该退化归因于替站触发。详见 reporting/WORST_CASE.md 的逐动作证据和推断边界。', '',
  '候选960局的停止证书包括714局真实Delaunay覆盖、70局动态连续单元覆盖、176局16源成功计数。六条最终公共日志（基线/候选各三条）无需隐藏布局均精确重放，见 qa/final_replay_summary.json。独立复核重新计算全部最终统计及区间，与主报告相符。']
 (ROOT/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({n:{k:s[k] for k in ('mean_s','p95_s','max_s','gain_ratio_of_means_pct','failed','timeouts')} for n,s in stats.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
