"""Generate reserved fixtures only after checking a written algorithm/configuration lock.
Evaluator-only fixture generator; strategy never imports this module.
"""
import argparse
import hashlib
import json
from pathlib import Path
from .cases import random_case


def main():
    p=argparse.ArgumentParser();p.add_argument('--lock',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();lock=json.loads(Path(args.lock).read_text());out=Path(args.output)
    if out.exists():raise RuntimeError('Do not overwrite validation fixtures')
    for path,digest in lock['code_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise RuntimeError('Locked code changed: '+path)
    cases=[]
    for seed in range(lock['seed_start'],lock['seed_stop_exclusive']):
        for mode in lock['error_modes']:
            case=random_case(seed,mode);case['id']=case['id'].replace('dev_','holdout_',1);cases.append(case)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(cases,indent=2),encoding='utf-8')
    print('Generated',len(cases),'held-out configurations after lock; SHA256',hashlib.sha256(out.read_bytes()).hexdigest())

if __name__=='__main__':main()
