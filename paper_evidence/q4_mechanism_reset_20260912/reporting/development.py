"""Create traceable per-round conclusions from every unfiltered development run."""
import json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
index=json.loads((ROOT/'round_index.json').read_text())
rows=[]
for item in index:
 folder=ROOT/item['round']; path=folder/'development/comparison.json'
 if not path.exists():continue
 comparison=json.loads(path.read_text()); stats=comparison['configurations']; base=stats['BASE25']
 summary=json.loads((folder/'development/summary.json').read_text())
 details=[]
 lines=[f"# {item['round']} 开发结论",'',item['motivation'],'', '|方案|完整/局数|失败|超时|均值秒|P95秒|最差秒|均值收益|', '|---|---:|---:|---:|---:|---:|---:|---:|']
 for name in item['configs']:
  s=stats[name]; significant=s['gain_ratio_of_means_pct']>=5 and s['complete']/s['runs']>=base['complete']/base['runs'] and s['p95_s']<=base['p95_s']
  lines.append(f"|{name}|{s['complete']}/{s['runs']}|{s['failed']}|{s.get('timeouts',0)}|{s['mean_s']:.2f}|{s['p95_s']:.2f}|{s['max_s']:.2f}|{s['gain_ratio_of_means_pct']:.3f}%|")
  if name not in ('BASE25','HIST_ADAPT'):
   events=Counter()
   for r in summary['rows']:
    if r['config']==name:events.update(r['event_counts'])
   row=dict(round=item['round'],config=name,primary=name==item['primary'],significant=significant,**{k:s[k] for k in ('gain_ratio_of_means_pct','complete','runs','failed','p95_s','mean_s','max_s')},events=dict(events))
   rows.append(row)
   details += ['',f"{name}：{'达到开发筛选门槛，需独立验证' if significant else '未达到 5% / 成功率 / P95 联合门槛；不替换推荐'}。",
      f"最差绝对案例 `{s['worst_case']}`；最差配对退化 {s['worst_gain_pct']:.3f}%。",
      '动作耗时分解（秒/局）：'+json.dumps(s['components'],ensure_ascii=False),
      '相对基线动作差（秒/局）：'+json.dumps({k:round(v-base['components'].get(k,0),3) for k,v in s['components'].items()},ensure_ascii=False),
      '机制事件总次数：'+json.dumps(dict(events),ensure_ascii=False)]
 lines += details
 lines += ['','源码/configs、每局 actions.jsonl/strategy.jsonl/result.json 及失败堆栈均位于 development/。上表没有剔除失败、慢例或无触发案例。组合/证书消融不单独计轮。', '', '证据等级：完整性来自保守几何与有限原覆盖/光学兜底；时间收益或退化仅获本开发集实验支持。未证明整局最优，未验证官方分布或官方运行。']
 (folder/'REVIEW.md').write_text('\n'.join(lines)+'\n')
(ROOT/'development_evidence.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print(json.dumps(rows,ensure_ascii=False,indent=2))
