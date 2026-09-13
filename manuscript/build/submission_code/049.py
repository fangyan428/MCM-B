"""Run the predeclared ten development rounds, retaining every attempted run."""
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    progress=[]
    for row in json.loads((ROOT/'round_index.json').read_text()):
        folder=ROOT/row['round']
        command=[sys.executable,'-m','paper_evidence.q4_mechanism_reset_20260912.experiment',
                 '--configs',str(folder/'configs.json'),'--output',str(folder/'development'),
                 '--seed','291000','--count','24','--error-modes','spatial_hash,positive,negative,smooth',
                 '--roundings','bounded','--workers','4','--stage','development','--reference','BASE25']
        (folder/'command.json').write_text(json.dumps(command,indent=2))
        with (folder/'execution.log').open('x') as output:
            result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT)
        progress.append(dict(round=row['round'],exit_code=result.returncode))
        (ROOT/'development_progress.json').write_text(json.dumps(progress,indent=2))
        comparison=folder/'development/comparison.json'
        if comparison.exists():
            stats=json.loads(comparison.read_text())['configurations']
            compact={name:{k:s[k] for k in ('complete','runs','mean_s','p95_s','gain_ratio_of_means_pct')} for name,s in stats.items()}
            print(json.dumps(dict(round=row['round'],results=compact)),flush=True)
        else:
            print(json.dumps(dict(round=row['round'],framework_failure=True,exit=result.returncode)),flush=True)
            raise SystemExit(result.returncode or 1)


if __name__=='__main__':main()
