"""Sequential HTTP adapter, idempotent retries, accepted-only accounting.
This client cannot select official rehearsal vs formal mode: the UI does that.
"""
import json
import math
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class ProtocolError(RuntimeError):pass
class TransportUncertain(RuntimeError):pass

class JsonlLog:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('w',encoding='utf-8')
    def __call__(self,row):
        self.file.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');self.file.flush()
    def close(self):self.file.close()

class HttpTransport:
    def __init__(self,base_url):self.base_url=base_url.rstrip('/')
    def request(self,path,payload,timeout):
        req=Request(self.base_url+path,data=json.dumps(payload,allow_nan=False).encode('utf-8'),
                    headers={'Content-Type':'application/json'},method='POST')
        try:
            with urlopen(req,timeout=timeout) as r:return r.status,json.load(r)
        except HTTPError as e:
            try:body=json.load(e)
            except (ValueError,UnicodeError):body={}
            return e.code,body

class Client:
    def __init__(self,transport,robot_id,log=lambda data:None,reserve_s=5.,retries=2):
        self.transport=transport;self.robot_id=robot_id;self.log=log;self.reserve=reserve_s;self.retries=retries
        self.position=(0.,0.);self.channel=1;self.virtual=0.;self.deadline=None;self.max_virtual=360000
        self.session=uuid.uuid4().hex;self.sequence=0;self.entered=False;self.closed=False;self.poisoned=False
        self.parts=dict(movement_s=0.,switch_s=0.,detection_s=0.,optical_s=0.,laser_s=0.)
        self.phases={};self.counts=dict(measure=0,clear=0,clear_success=0,clear_failure=0,retries=0)
    def _call(self,path,position=None,channel=None,phase='control'):
        if self.closed or self.poisoned:raise ProtocolError('Client closed or previous action uncertain')
        if path!='/enter' and not self.entered:raise ProtocolError('Not entered')
        now=time.monotonic()
        if self.deadline is not None and now>=self.deadline-(0 if path=='/exit' else self.reserve):
            raise ProtocolError('Real deadline guard reached; completion not certified')
        self.sequence+=1
        body=dict(arena_id='default',robot_id=self.robot_id,request_id=f'{self.session}-{self.sequence}')
        move=0.;switch=0.
        if position is not None:
            x,y=map(float,position)
            if not all(math.isfinite(z) and abs(z)<=2000000 for z in (x,y)):
                raise ValueError('Invalid position')
            if not isinstance(channel,int) or isinstance(channel,bool) or not 1<=channel<=20:raise ValueError('Invalid channel')
            body.update(position=dict(x=x,y=y),channel=channel)
            move=math.dist(self.position,(x,y))/5
            switch=float(path=='/measure' and self.channel!=channel)
            if self.virtual+move+switch+5>=self.max_virtual:
                raise ProtocolError('Virtual deadline guard reached')
        start=time.monotonic()
        for attempt in range(self.retries+1):
            self.log(dict(type='request',path=path,payload=body,attempt=attempt,phase=phase))
            try:
                timeout=5. if self.deadline is None else max(.001,min(5.,self.deadline-time.monotonic()))
                status,r=self.transport.request(path,body,timeout)
                if not isinstance(r,dict):raise ValueError('Response is not an object')
                self.log(dict(type='response',path=path,request_id=body['request_id'],http_status=status,response=r,attempt=attempt))
                break
            except (OSError,URLError,ValueError,UnicodeError) as exc:
                self.log(dict(type='transport_error',request_id=body['request_id'],error=str(exc),attempt=attempt))
                if attempt==self.retries or (self.deadline is not None and time.monotonic()>=self.deadline):
                    self.poisoned=True;raise TransportUncertain('Same-ID retries exhausted; action state unknown') from exc
                self.counts['retries']+=1
        if status!=200 or r.get('accepted') is not True:
            self.poisoned=True
            raise ProtocolError(f'HTTP {status}, accepted={r.get("accepted")}; clock retained at {self.virtual}')
        vt=r.get('virtual_time_s')
        if isinstance(vt,bool) or not isinstance(vt,(int,float)) or not math.isfinite(vt) or vt<self.virtual:
            self.poisoned=True;raise ProtocolError('Invalid virtual clock')
        delta=dict(movement_s=move,switch_s=switch,detection_s=0.,optical_s=0.,laser_s=0.)
        if path=='/enter':
            remaining=r.get('remaining_real_duration_s')
            if not isinstance(remaining,(int,float)) or isinstance(remaining,bool) or not 0<=remaining<=1200:
                raise ProtocolError('Missing/invalid remaining_real_duration_s')
            self.deadline=start+remaining;self.max_virtual=float(r['max_virtual_duration_s']);self.entered=True
        elif path=='/measure':
            kind=r.get('measure_result')
            if kind not in ('direction','near','no_signal'):raise ProtocolError('Invalid measure response')
            if kind=='direction' and (not isinstance(r.get('svd_deg'),(int,float)) or not 0<=r['svd_deg']<360):
                raise ProtocolError('Invalid bearing')
            delta['detection_s']=5.;self.channel=channel;self.counts['measure']+=1
        elif path=='/clear':
            kind=r.get('clear_result')
            if kind not in ('success','no_target_in_range'):raise ProtocolError('Invalid clear response')
            delta['optical_s']=3.;delta['laser_s']=2.*(kind=='success');self.counts['clear']+=1
            self.counts['clear_success' if kind=='success' else 'clear_failure']+=1
        elif path=='/exit':
            if r.get('exit_reason')!='user_exit':raise ProtocolError('Invalid exit response')
            self.closed=True
        if position is not None:self.position=(x,y)
        for k,value in delta.items():self.parts[k]+=value
        self.phases[phase]=self.phases.get(phase,0)+sum(delta.values())
        self.virtual=float(vt)
        if abs(sum(self.parts.values())-self.virtual)>max(1e-4,self.sequence*1e-6):
            self.poisoned=True;raise ProtocolError('Virtual-time accounting mismatch')
        return r
    def enter(self):return self._call('/enter')
    def measure(self,p,c,phase='measure'):return self._call('/measure',p,c,phase)
    def clear(self,p,c,phase='clear'):return self._call('/clear',p,c,phase)
    def exit(self):return self._call('/exit')
    def metrics(self):return dict(virtual_time_s=self.virtual,components=self.parts.copy(),phases=self.phases.copy(),counts=self.counts.copy())
