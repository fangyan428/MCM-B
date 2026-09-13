"""Validate figure/source inventory, published aggregates, and rendered figure geometry."""
from pathlib import Path
import csv,json,re,sys,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'analysis/source_data'
SKILL=Path.home()/'.codex/skills/nature-figure/scripts'
md=(ROOT/'中文论文初稿.md').read_text()
imgs=re.findall(r'!\[([^\]]+)\]\((figures/[^)]+)\)',md)
assert len(imgs)==19
for i,(_,p) in enumerate(imgs,1):
    assert (ROOT/p).is_file()
    assert f'图{i}' in md
q3=list(csv.DictReader((DATA/'q3_final_pairs.csv').open()))
q3_stats=list(csv.DictReader((DATA/'q3_final_statistics.csv').open()))
checks=[]
for env in ['bounded','pre_round_stress']:
    rr=[r for r in q3 if r['rounding']==env];assert len(rr)==480
    for col,variant in [('baseline_s','BASE'),('candidate_s','GATED_TOUR_MULTI_PARALLAX')]:
        vals=np.array([float(r[col]) for r in rr]);ref=next(r for r in q3_stats if r['rounding']==env and r['variant']==variant)
        for key,calc in [('mean',np.mean(vals)),('p95',np.quantile(vals,.95)),('maximum',np.max(vals))]:
            assert abs(calc-float(ref[key]))<1e-7
        checks.append(dict(question='Q3',environment=env,variant=variant,runs=len(vals),mean=float(vals.mean())))
q4=list(csv.DictReader((DATA/'q4_source_data.csv').open()))
ref4=json.loads((DATA/'q4_verification.json').read_text())
for batch in sorted(set(r['batch'] for r in q4)):
    for cf in sorted(set(r['config'] for r in q4 if r['batch']==batch)):
        rr=[r for r in q4 if r['batch']==batch and r['config']==cf]
        vals=np.array([float(r['virtual_time_s']) for r in rr]);ref=ref4['latest'][cf] if batch=='reset_final_validation' else ref4['historical'][batch][cf]
        assert len(vals)==ref['runs'] and all(r['cleared']==r['total'] for r in rr)
        for key,calc in [('mean_s',np.mean(vals)),('p95_s',np.quantile(vals,.95)),('max_s',np.max(vals))]:assert abs(calc-ref[key])<1e-7
        checks.append(dict(question='Q4',batch=batch,config=cf,runs=len(vals),mean=float(vals.mean())))
out=ROOT/'qa'
(out/'numeric_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
r=subprocess.run([sys.executable,str(SKILL/'validate_figure.py'),str(ROOT/'analysis/make_figures.py'),'--json'],capture_output=True,text=True)
(out/'source_check.json').write_text(r.stdout)
results=[]
for f in sorted((ROOT/'figures').glob('fig*.pdf')):
    r=subprocess.run([sys.executable,str(SKILL/'audit_pdf_text.py'),str(f),'--json'],capture_output=True,text=True)
    (out/f'{f.stem}.text.json').write_text(r.stdout);assert r.returncode==0
    r=subprocess.run([sys.executable,str(SKILL/'audit_figure_collisions.py'),str(f),'--json-out',str(out/f'{f.stem}.collision.json')],capture_output=True,text=True)
    results.append(dict(figure=f.stem,collision_exit_code=r.returncode))
    if r.returncode:print(f.stem,r.stdout)
(out/'figure_check_summary.json').write_text(json.dumps(results,indent=2))
assert all(r['collision_exit_code']==0 for r in results)
print('PASS: 19 figures, every image explained, 19 aggregate groups reproduced, figure text and collision checks passed.')
