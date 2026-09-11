"""Extract the immutable runtime and execute representative self cases from there."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def main():
    root=Path.cwd();archive=root/'question3/releases/q3_omni_round13.zip'
    script='''import json,hashlib
from pathlib import Path
from question3.cases import random_case,late_source_case,clustered_case
from question3.simulator import Simulator
from question3.interface import Client,JsonlLog
from question3.strategy import run
from question3.audit import audit_folder
c=json.loads(Path('question3/configs/recommended_omni.json').read_text())
lock=json.loads(Path('question3/results/round13_lock.json').read_text())
assert c==lock['configs']['BOTH']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
rows=[]
for case in [random_case(0,'negative'),random_case(1,'smooth'),late_source_case(),clustered_case()]:
 folder=Path('smoke')/case['id'];folder.mkdir(parents=True)
 actions=JsonlLog(folder/'actions.jsonl');events=JsonlLog(folder/'strategy.jsonl')
 env=Simulator(case);r=run(Client(env,'SELF',actions),c,events);actions.close();events.close()
 assert r['status']=='complete' and not env.evaluation()['remaining_channels']
 (folder/'evaluator_hidden_case.json').write_text(json.dumps(case))
 (folder/'result.json').write_text(json.dumps(dict(summary=dict(rounding='bounded'),strategy=r)))
 es=list(map(json.loads,(folder/'strategy.jsonl').read_text().splitlines()))
 rows.append(dict(case=case['id'],virtual_s=r['metrics']['virtual_time_s'],radius_skips=sum(e['type']=='certified_clear_skip' and 'radius_prior' in e for e in es),certificate=r['stopping_certificate']['method'],audit_actions=audit_folder(folder)))
assert rows[0]['radius_skips']==3 and rows[1]['radius_skips']==1
print(json.dumps(rows))
'''
    with tempfile.TemporaryDirectory(prefix='q3-round13-release-') as temp:
        with ZipFile(archive) as z:
            assert not [i for i in z.infolist() if not i.file_size and 'round13' in i.filename]
            z.extractall(temp)
        result=subprocess.run([sys.executable,'-c',script],cwd=temp,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        data=dict(kind='SELF_EXTRACTED_RELEASE_SMOKE',zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  code_and_config_match_lock=True,cases=json.loads(result.stdout),official_runs=0,formal_runs=0)
    (root/'question3/results/round13_release_package_smoke.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__':main()
