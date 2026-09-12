"""Select from development only, lock sources, THEN generate the final fixtures."""
import datetime
import hashlib
import json
from pathlib import Path
from .fixtures import generate

ROOT=Path(__file__).resolve().parent
NAMES=['NEAREST_SHARED_PARALLAX','TOUR_SHARED_PARALLAX','GATED_TOUR_MULTI_PARALLAX','GATED_TOUR_SHARED_PARALLAX','COVER_TOUR_SHARED_PARALLAX']
OLD={'NEAREST_SHARED_PARALLAX':'round06_belief_tour','TOUR_SHARED_PARALLAX':'round06_belief_tour',
     'GATED_TOUR_SHARED_PARALLAX':'round09_information','COVER_TOUR_SHARED_PARALLAX':'round10_continuous_cover',
     'GATED_TOUR_MULTI_PARALLAX':'ablation'}
ABLATIONS=['GATED_TOUR_SHARED','TOUR_REFRESH_PARALLAX','GATED_TOUR_MULTI_PARALLAX','GATED_NEAREST_SHARED_PARALLAX']

def main():
    out=ROOT/'validation_lock.json'
    if out.exists():raise RuntimeError('Refusing to replace existing final-validation lock')
    scores={};eligible=[]
    for name in NAMES:
        batches=[]
        for folder in [OLD[name],('ablation_expanded' if name=='GATED_TOUR_MULTI_PARALLAX' else 'expanded_development')]:
            for rounding in ['bounded','pre_round_stress']:
                rows=json.loads((ROOT/folder/rounding/'comparison.json').read_text())
                batches.append(dict(batch=f'{folder}/{rounding}',reference=rows['BASE'],candidate=rows[name]))
        score=sum(b['candidate']['mean']/b['reference']['mean'] for b in batches)/4
        passed=all(b['candidate']['significant'] for b in batches)
        scores[name]=dict(score=score,passed=passed,batches=batches)
        if passed:eligible.append(name)
    selected=min(eligible or NAMES,key=lambda n:(scores[n]['score'],NAMES.index(n)))
    config=json.loads((ROOT/'frozen/question3/configs/recommended_omni.json').read_text())
    variants=list(dict.fromkeys(['BASE',selected]+[n for n in NAMES+ABLATIONS if n!=selected]))
    configs={n:(config if n=='BASE' else dict(baseline_config=config,mechanism=n.lower())) for n in variants}
    runtime=['strategy.py','geometry.py','routing.py','coverage.py','coverage_audit.py','experiment.py','fixtures.py','__init__.py']
    frozen=json.loads((ROOT/'freeze_manifest.json').read_text())['sha256']
    lock=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=selected,
        eligibility=bool(eligible),selection_scores=scores,configs=configs,
        code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in runtime},
        baseline_sha256=frozen,final_seed_start=910000,final_layout_count=120,
        outcome_rule='Selected only: per rounding mean <= .95*BASE, success >= BASE, P95 <= BASE. No validation reselection.',
        bootstrap='20000 paired stratified layout-block resamples; error modes never treated as independent layouts',
        official_runs=0,formal_runs=0)
    out.write_text(json.dumps(lock,ensure_ascii=False,indent=2))
    (ROOT/'best_candidate.json').write_text(json.dumps(configs[selected],indent=2))
    fixtures=ROOT/'final_validation_cases.json'
    if fixtures.exists():raise RuntimeError('Final fixtures already exist; cannot claim unseen generation')
    fixtures.write_text(json.dumps(generate(910000,120,'final'),indent=2))
    (ROOT/'validation_generation.json').write_text(json.dumps(dict(
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        after_lock_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
        fixtures_sha256=hashlib.sha256(fixtures.read_bytes()).hexdigest(),layouts=120,case_error_pairs=480),indent=2))
    print(json.dumps(dict(selected=selected,scores={n:dict(score=s['score'],passed=s['passed']) for n,s in scores.items()}),indent=2))

if __name__=='__main__':main()
