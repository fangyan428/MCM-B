"""Post-lock evaluation only: never called by any decision policy."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .experiment import ROOT,aggregate,dump

ROUNDS={
 'round01_homing':('HOMING','BASE','中心直进虽然安全，但径向折返和旧任务评分增加移动；不采用单项。'),
 'round02_parallax':('PARALLAX','HOMING','视差改善中心逼近，却未单独胜过冻结基线；作为组合因素保留。'),
 'round03_refresh':('REFRESH_PARALLAX','PARALLAX','原地再观测单项仍失败；最终组合删除这一非必要步骤。'),
 'round04_shared':('SHARED_PARALLAX','REFRESH_PARALLAX','跨频道持续收缩减少重复定位，但仍需与新任务路线配合。'),
 'round05_strip':('STRIP','BASE','单方位有限光学条带覆盖很昂贵；完整放弃。'),
 'round06_belief_tour':('TOUR_SHARED_PARALLAX','SHARED_PARALLAX','首次显著突破来自新信息集合与路线调度共同工作；最近入口消融表明完整2-opt只贡献一部分。'),
 'round07_reception_bracket':('RECEPTION_BRACKET','BASE','边界成员查询可测距，但长距离往返压倒信息收益；放弃。'),
 'round08_survey':('SURVEY','BASE','固定多站信息网络增加搜索检测和聚集案例绕行；放弃。'),
 'round09_information':('GATED_TOUR_SHARED_PARALLAX','TOUR_SHARED_PARALLAX','相对直接父组合收益不足1%，不视作又一次5%突破；其有限观测价值证书与温和收益可留在候选。'),
 'round10_continuous_cover':('COVER_TOUR_SHARED_PARALLAX','TOUR_SHARED_PARALLAX','开发轨迹完全一致，连续覆盖证书未产生收益；最终候选不包含此机制。'),
}

def comparison(folder,rounding):
    part='bounded_full' if folder=='round01_homing' and rounding=='bounded' else rounding
    return json.loads((ROOT/folder/part/'comparison.json').read_text())

def bootstrap(rows,selected):
    by={n:{r['case_id']:r for r in rows if r['variant']==n} for n in ['BASE',selected]}
    keys=sorted(by['BASE']);layouts={}
    for key in keys:
        seed=key.split('_')[-2] if key.endswith(('smooth','positive','negative')) else key.split('_')[-3]
        # Error mode spatial_hash has an underscore; source seed is reliable from the fixture id.
        seed=next(word for word in key.split('_') if word.isdigit())
        layouts.setdefault(seed,[]).append(key)
    fixtures=json.loads((ROOT/'final_validation_cases.json').read_text())
    family_by_seed={str(c['seed']):c['family'] for c in fixtures}
    seeds=sorted(layouts);data={n:np.asarray([[by[n][k]['penalized_virtual_s'] for k in sorted(layouts[s])] for s in seeds]) for n in by}
    assert all(len(layouts[s])==4 for s in seeds)
    rng=np.random.default_rng(20260912);indices=[]
    for family in sorted(set(family_by_seed.values())):
        ids=np.array([i for i,s in enumerate(seeds) if family_by_seed[s]==family])
        indices.append(rng.choice(ids,size=(20000,len(ids)),replace=True))
    idx=np.concatenate(indices,axis=1)
    means={n:data[n].mean(axis=1)[idx].mean(axis=1) for n in by}
    change=100*(means[selected]/means['BASE']-1)
    p95={n:np.percentile(data[n][idx].reshape(20000,-1),95,axis=1) for n in by}
    return dict(layouts=len(seeds),resamples=20000,mean_change_pct_ci95=np.percentile(change,[2.5,97.5]).tolist(),
                p95_change_seconds_ci95=np.percentile(p95[selected]-p95['BASE'],[2.5,97.5]).tolist(),
                bootstrap_fraction_mean_improvement_ge5=float(np.mean(change<=-5)))

def main():
    lock=json.loads((ROOT/'validation_lock.json').read_text());selected=lock['selected']
    evidence=dict(selected=selected,final={},rounds={},scope_audit={})
    for folder,(variant,parent,reason) in ROUNDS.items():
        batches={}
        for rounding in ['bounded','pre_round_stress']:
            table=comparison(folder,rounding)
            source=table
            if parent not in table:
                parent_folder='round02_parallax' if parent=='PARALLAX' else 'round04_shared'
                source=comparison(parent_folder,rounding)
            batches[rounding]=dict(candidate=table[variant],baseline=table['BASE'],parent=source[parent],
                direct_parent_mean_change_pct=100*(table[variant]['mean']/source[parent]['mean']-1))
        evidence['rounds'][folder]=dict(variant=variant,parent=parent,reason=reason,batches=batches)
        lines=[f'# {folder} 完整开发复核', '', reason, '', '| 舍入 | BASE均值 | 候选均值 | 对BASE变化 | 直接父方案变化 | BASE P95 | 候选P95 | 候选最大 | 完整/总局 | 失败/超时 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r,x in batches.items():
            a,b=x['baseline'],x['candidate']
            lines.append(f'| {r} | {a["mean"]:.2f} | {b["mean"]:.2f} | {b["mean_change_pct"]:+.2f}% | {x["direct_parent_mean_change_pct"]:+.2f}% | {a["p95"]:.2f} | {b["p95"]:.2f} | {b["maximum"]:.2f} | {b["complete"]}/{b["runs"]} | {b["failed"]}/{b["timeouts"]} |')
        lines += ['', '以上单位为总虚拟秒。所有场景配对、不删除失败。完整配置、源码快照、动作/反馈/策略日志与每种方案的耗时分解在对应舍入目录；R1主批使用bounded_full，bounded保留最初4例探针。', '', '原理与证明范围见 ../THEORY.md；本表是开发证据，不是最终验证。R9和R10继承父组合已超过基线的收益，不能冒称新增机制再次带来≥5%改善。']
        (ROOT/folder/'REVIEW.md').write_text('\n'.join(lines)+'\n')
    all_paired=[]
    for rounding in ['bounded','pre_round_stress']:
        path=ROOT/'final_validation'/rounding
        rows=json.loads((path/'summary.json').read_text())['rows']
        assert len(rows)==480*8,('Incomplete final matrix',rounding,len(rows))
        configs=json.loads((path/'configs.json').read_text())
        for n,c in configs.items():assert c==lock['configs'][n]
        snap=json.loads((path/'code_sha256.json').read_text())
        for p,h in lock['code_sha256'].items():assert snap[p]==h
        meta=json.loads((path/'metadata.json').read_text())
        fixtures=json.loads((ROOT/'final_validation_cases.json').read_text())
        for case in fixtures:assert meta['case_sha256'][case['id']]==hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()
        by={n:{r['case_id']:r for r in rows if r['variant']==n} for n in configs}
        assert all(len(rs)==480 for rs in by.values())
        family={}
        for f in sorted({c['family'] for c in fixtures}):
            ids={c['id'] for c in fixtures if c['family']==f}
            family[f]=aggregate([r for r in rows if r['case_id'] in ids])
        pairs=[]
        for case_id,b in by['BASE'].items():
            c=by[selected][case_id]
            pair=dict(rounding=rounding,case_id=case_id,baseline=b['penalized_virtual_s'],candidate=c['penalized_virtual_s'],
                change_s=c['penalized_virtual_s']-b['penalized_virtual_s'],
                change_pct=100*(c['penalized_virtual_s']/b['penalized_virtual_s']-1),
                baseline_success=b['success'],candidate_success=c['success'])
            for k in b['metrics']['components']:pair[k+'_difference']=c['metrics']['components'][k]-b['metrics']['components'][k]
            pairs.append(pair)
        all_paired.extend(pairs)
        worst=sorted(pairs,key=lambda p:p['change_pct'],reverse=True)[:10]
        evidence['final'][rounding]=dict(aggregates=aggregate(rows),families=family,bootstrap=bootstrap(rows,selected),
            worst_regressions=worst,better=sum(p['change_s']<-1e-6 for p in pairs),
            worse=sum(p['change_s']>1e-6 for p in pairs),actions=sum(r.get('audited_actions',0) for r in rows),
            winner_event_counts={k:sum(r.get('event_counts',{}).get(k,0) for r in by[selected].values())
                for k in sorted(set().union(*(r.get('event_counts',{}) for r in by[selected].values())))})
    with (ROOT/'final_paired.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(all_paired[0]));w.writeheader();w.writerows(all_paired)
    frozen=json.loads((ROOT/'freeze_manifest.json').read_text())['sha256']
    repo=ROOT.parents[1]
    assert all(hashlib.sha256((repo/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
    assert all(hashlib.sha256((ROOT/'frozen'/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
    parity=0
    for old,new in [('round19_dev_main','bounded_full'),('round19_dev_rounding','pre_round_stress')]:
        original=json.loads((repo/'question3/results'/old/'summary.json').read_text())['cases']
        reference={r['case_id']:r for r in original if r['variant']=='BOTH'}
        fresh=json.loads((ROOT/'round01_homing'/new/'summary.json').read_text())['rows']
        for r in fresh:
            if r['variant']=='BASE':
                other=reference[r['case_id']]
                assert r['metrics']==other['metrics'] and r['cleared']==other['cleared'] and r['status']==other['status']
                parity+=1
    inventory=[]
    for path in sorted(ROOT.glob('*/*/summary.json')):
        if 'rows' not in (data:=json.loads(path.read_text())):continue
        rows=data['rows']
        inventory.append(dict(path=str(path.parent.relative_to(ROOT)),runs=len(rows),
            failures=sum(not r['success'] for r in rows),timeouts=sum(r['timeout'] for r in rows),
            false_completes=sum(r['false_complete'] for r in rows),actions=sum(r.get('audited_actions',0) for r in rows)))
    evidence['scope_audit']=dict(frozen_and_recommendation_unchanged=True,old_baseline_exact_matches=parity,
        total_matrix_runs=sum(r['runs'] for r in inventory),failures=sum(r['failures'] for r in inventory),
        timeouts=sum(r['timeouts'] for r in inventory),false_completes=sum(r['false_completes'] for r in inventory),
        audited_actions=sum(r['actions'] for r in inventory),inventory=inventory,official_runs=0,formal_runs=0)
    evidence['replacement_gate_passed']=all(x['aggregates'][selected]['significant'] for x in evidence['final'].values())
    dump(ROOT/'FINAL_EVIDENCE.json',evidence)
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['rounds','scope_audit','final']},indent=2))
    for rounding,x in evidence['final'].items():
        print(rounding,json.dumps(dict(base=x['aggregates']['BASE']['mean'],candidate=x['aggregates'][selected]['mean'],
             change=x['aggregates'][selected]['mean_change_pct'],p95=x['aggregates'][selected]['p95'],bootstrap=x['bootstrap']),indent=2))

if __name__=='__main__':main()
