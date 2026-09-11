"""Actually exercise rejection of a forged domain range certificate after a run."""
import json
from pathlib import Path
import shutil
import tempfile
from question3.audit import audit_folder


def main():
    source=Path('question3/results/round18_dev_main/DOMAIN/dev_0_spatial_hash')
    original=json.loads((source/'result.json').read_text())
    index=next(i for i,r in enumerate(original['strategy']['regions']) if r['selection']['mode'].startswith('domain_'))
    rows=[]
    for corruption in ['understate_range','fake_offset']:
        with tempfile.TemporaryDirectory(prefix='round18-forged-proof-') as tmp:
            folder=Path(tmp)/'case';shutil.copytree(source,folder)
            data=json.loads((folder/'result.json').read_text());selection=data['strategy']['regions'][index]['selection']
            if corruption=='understate_range':selection['source_range_upper_m']=6
            else:selection['offset']=[0,0]
            (folder/'result.json').write_text(json.dumps(data))
            try:audit_folder(folder)
            except AssertionError:rows.append(dict(corruption=corruption,rejected=True))
            else:raise AssertionError('Forged certificate accepted')
    Path('question3/results/round18_tamper_audit.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
