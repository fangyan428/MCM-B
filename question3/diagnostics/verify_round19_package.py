"""Extract the immutable runtime and execute representative self cases from there."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def main():
    root=Path.cwd();archive=root/'question3/releases/q3_omni_round19.zip'
    script='''import json,hashlib
from pathlib import Path
from question3.cases import random_case,late_source_case,clustered_case
from question3.simulator import Simulator
from question3.interface import Client,JsonlLog
from question3.strategy import run
from question3.audit import audit_folder
c=json.loads(Path('question3/configs/recommended_omni.json').read_text())
lock=json.loads(Path('question3/results/round19_lock.json').read_text())
assert c==lock['configs']['BOTH']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
rows=[]
fresh=json.loads(Path('question3/results/round19_holdout_cases.json').read_text())+json.loads(Path('question3/results/round19_outer_holdout_cases.json').read_text())
worst=[c for c in fresh if c['id'] in ('holdout_250022_positive','outer_holdout_260007_negative','holdout_250019_negative','outer_holdout_260006_negative')]
assert len(worst)==4
for case in [random_case(0,'negative'),random_case(1,'smooth'),late_source_case(),clustered_case()]+worst:
 folder=Path('smoke')/case['id'];folder.mkdir(parents=True)
 actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
 env=Simulator(case);r=run(Client(env,'SELF',actions),c,events);actions.close();events.close()
 assert r['status']=='complete' and not env.evaluation()['remaining_channels']
 (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
 (folder/'result.json').write_text(json.dumps(dict(summary=dict(rounding='bounded'),strategy=r)))
 es=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
 tasks=[e for e in es if e['type']=='schedule']
 assert len(tasks)<=23 and not any(e.get('forced',False) for e in tasks)
 rows.append(dict(domain_shared=sum(e['type']=='localization' and e['selection']['mode']=='domain_shared' for e in es),tasks=len(tasks),case=case['id'],virtual_s=r['metrics']['virtual_time_s'],radius_skips=sum(e['type']=='certified_clear_skip' and 'radius_prior' in e for e in es),certificate=r['stopping_certificate']['method'],audit_actions=audit_folder(folder)))
assert rows[2]['certificate']=='seven_station_channel_cover'
assert rows[3]['certificate']=='source_count_upper_bound' and rows[3]['domain_shared']==15
print(json.dumps(rows))
'''
    with tempfile.TemporaryDirectory(prefix='q3-round19-release-') as temp:
        with ZipFile(archive) as z:
            assert not [i for i in z.infolist() if not i.file_size and 'round19' in i.filename]
            z.extractall(temp)
        result=subprocess.run([sys.executable,'-c',script],cwd=temp,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        data=dict(kind='SELF_EXTRACTED_RELEASE_SMOKE',zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  code_and_config_match_lock=True,cases=json.loads(result.stdout),official_runs=0,formal_runs=0)
    (root/'question3/results/round19_release_package_smoke.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__':main()
