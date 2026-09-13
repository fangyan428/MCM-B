"""Replay a policy with responses only: no simulated world or hidden case object."""
import json
import math
from pathlib import Path
from .experiment import ROOT,PublicClient
from .strategy import run
from question3.interface import Client

class TranscriptTransport:
    def __init__(self,path):
        requests={};self.steps=[];self.i=0;seen=set()
        for row in map(json.loads,path.read_text().splitlines()):
            if row['type']=='request':requests[row['payload']['request_id']]=row
            if row['type']=='response' and row['response'].get('accepted'):
                rid=row['request_id']
                if rid not in seen:self.steps.append((requests[rid],row));seen.add(rid)
    def request(self,path,payload,timeout=5):
        req,response=self.steps[self.i];self.i+=1
        assert path==req['path']
        expected=req['payload']
        for key in ('channel','position'):
            if key in expected:
                if key=='position':
                    assert math.dist(list(payload[key].values()),list(expected[key].values()))<1e-7
                else:assert payload[key]==expected[key]
        return response['http_status'],dict(response['response'])

def main():
    selected=json.loads((ROOT/'validation_lock.json').read_text())['selected']
    cfg=json.loads((ROOT/'best_candidate.json').read_text())
    # The ablation matrix contains both possible selected gate variants and adverse cases.
    cases=['boundary_minR_16','late_channel20_after_ten','clustered_16']
    rows=[]
    for case in cases:
        folder=ROOT/'ablation/bounded'/selected/case
        transport=TranscriptTransport(folder/'actions.jsonl')
        result=run(PublicClient(Client(transport,'SELF')),cfg)
        original=json.loads((folder/'result.json').read_text())['strategy']
        assert result['status']=='complete' and result['cleared_channels']==original['cleared_channels']
        assert result['metrics']==original['metrics']
        assert transport.i==len(transport.steps)
        rows.append(dict(case=case,matched_actions=transport.i,virtual_time_s=result['metrics']['virtual_time_s'],world_object_present=False))
    (ROOT/'public_transcript_replay.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
