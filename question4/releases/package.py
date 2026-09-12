"""Build and verify local Q4 deliverables, without touching historical Q3 evidence."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'question4/releases'

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    os.chdir(ROOT)
    from question4.experiment import source_hashes
    locked=json.loads(Path('question4/results/round9_main/lock.json').read_text())
    assert source_hashes()==locked['code_sha256']
    deps=[Path('question3')/n for n in ('__init__.py','interface.py','self_server.py','simulator.py','cases.py')]
    all_files=sorted(p for p in Path('question4').rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'releases' not in p.parts)
    core=[p for p in all_files if 'results' not in p.parts]
    for batch in ('round9_main','round9_rounding'):
        core += [Path('question4/results')/batch/n for n in ('lock.json','fixtures.json','summary.json','comparison.json')]
    core += [Path('question4/results')/n for n in ('round9_review.json','experiment_index.json','representative_negative_cases.json','tests_final.txt','negative21_counterexample.json')]
    core.append(Path('question4/results/round9_main/FINAL/uniform_111000_spatial_hash/result.json'))
    core=sorted(set(core+deps))
    hashes={str(p):digest(p) for p in core}
    package=OUT/'q4_recommended.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in core:z.write(p,str(p))
        z.writestr('PACKAGE_MANIFEST.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('PACKAGE_MANIFEST.json'))
        for name,sha in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==sha
        with tempfile.TemporaryDirectory(prefix='q4_release_verify_') as tmp:
            z.extractall(tmp)
            code='''import json
from pathlib import Path
from question4.strategy import run
from question4.simulator import Simulator
from question4.audit import audit
from question3.interface import Client
fixture=json.loads(Path('question4/results/round9_main/fixtures.json').read_text())[0]
config=json.loads(Path('question4/configs/recommended.json').read_text())
records=[];client=Client(Simulator(fixture),'SELF',records.append);result=run(client,config)
checked=audit(fixture,records,result)
rows=json.loads(Path('question4/results/round9_main/summary.json').read_text())['rows']
reference=next(r for r in rows if r['config']=='FINAL' and r['case_id']==fixture['id'])
assert result['metrics']==reference['metrics']
print(json.dumps(dict(status=result['status'],case_id=fixture['id'],audit=checked,exact_metrics_match=True)))
'''
            proc=subprocess.run([sys.executable,'-c',code],cwd=tmp,capture_output=True,text=True,check=True)
            verification=json.loads(proc.stdout)
    print('Recommended ZIP verified, exact heldout-fixture replay passed',flush=True)
    evidence_files=sorted(set(all_files+deps+[Path(__file__).relative_to(ROOT)]))
    evidence_manifest={str(p):digest(p) for p in evidence_files}
    archive=OUT/'q4_experiment_evidence.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=5) as tar:
        for p in evidence_files:tar.add(p,arcname=str(p),recursive=False)
        data=json.dumps(evidence_manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE_MANIFEST.json');info.size=len(data)
        tar.addfile(info,io.BytesIO(data))
    verified=0
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            if member.name=='EVIDENCE_MANIFEST.json':continue
            assert member.isfile() and member.name in evidence_manifest
            f=tar.extractfile(member);h=hashlib.sha256()
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            assert h.hexdigest()==evidence_manifest[member.name]
            verified+=1
    assert verified==len(evidence_manifest)
    release=dict(recommended_config=json.loads(Path('question4/configs/recommended.json').read_text()),
        source_lock=locked['code_sha256'],package_verification=verification,evidence_files_verified=verified,
        self_runs=5376,official_rehearsals=0,formal_tests=0,artifacts={})
    for p in (package,archive):
        sha=digest(p);Path(str(p)+'.sha256').write_text(f'{sha}  {p.name}\n')
        release['artifacts'][p.name]=dict(sha256=sha,bytes=p.stat().st_size)
    (OUT/'recommended_manifest.json').write_text(json.dumps(release,ensure_ascii=False,indent=2))
    (OUT/'package_verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))
    print(json.dumps(release['artifacts'],indent=2),flush=True)
    print(f'All {verified} evidence files verified',flush=True)

if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    main()
