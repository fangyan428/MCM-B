"""SELF simulation of omnidirectional physics and valid-action protocol.
Not official simulator. No login/window UI/encrypted official log implementation.
Hidden case data stays here, evaluator accesses it only outside strategy execution.
"""
import copy
import hashlib
import json
import math
import time

class Simulator:
    def __init__(self,case,robot_id='SELF',remaining_s=1200,rounding='bounded'):
        self._sources=copy.deepcopy(case['sources']);self._seed=case.get('seed',0)
        self._error_mode=case.get('error_mode','spatial_hash');self._rounding=rounding
        self._robot_id=robot_id;self._cache={};self._entered=False;self._exited=False
        self._position=(0.,0.);self._channel=1;self._virtual_us=0;self._remaining=remaining_s;self._start=None
        self._cleared=set();self._components=dict(movement_s=0.,switch_s=0.,detection_s=0.,optical_s=0.,laser_s=0.)
        if len({s['channel'] for s in self._sources})!=len(self._sources):raise ValueError('Duplicate channel')
        for s in self._sources:
            if not 1<=s['channel']<=20 or not 1000<=s['radius']<=1500 or math.hypot(s['x'],s['y'])>1800+1e-7:
                raise ValueError('Invalid self case')
    def _response(self,accepted,**extra):
        return dict(accepted=accepted,real_timestamp_ms=int(time.time()*1000),
                    virtual_time_s=self._virtual_us/1e6 if accepted else 0,**extra)
    def _bias(self,p,c):
        x,y=p
        # IEEE signed zero describes the same physical location.
        if x==0:x=0.
        if y==0:y=0.
        if self._error_mode=='positive':return 1.
        if self._error_mode=='negative':return -1.
        if self._error_mode=='smooth':return math.sin(x/173+y/251+c+self._seed)
        if self._error_mode=='zero':return 0.
        if self._error_mode!='spatial_hash':raise ValueError('Unknown spatial error mode')
        # Same location and channel => same bias, independent of call count/time.
        data=f'{self._seed}:{c}:{float(x).hex()}:{float(y).hex()}'.encode()
        value=int.from_bytes(hashlib.sha256(data).digest()[:8],'big')
        return 2*value/(2**64-1)-1
    def _reading(self,p,s):
        true=math.degrees(math.atan2(s['y']-p[1],s['x']-p[0]))
        tick=round((true+self._bias(p,s['channel']))*100)
        if self._rounding=='bounded':
            # Honour the stated final +/-1deg bound and two-decimal serialization together.
            tick=min(math.floor((true+1)*100),max(math.ceil((true-1)*100),tick))
        elif self._rounding!='pre_round_stress':raise ValueError('Unknown rounding model')
        return (tick%36000)/100
    def request(self,path,payload,timeout=5.):
        b=copy.deepcopy(payload)
        if path not in ('/enter','/measure','/clear','/exit'):return 404,self._response(False)
        required={'arena_id','robot_id','request_id'}|({'position','channel'} if path in ('/measure','/clear') else set())
        if not required<=b.keys():return 400,self._response(False)
        if set(b)!=required or b['arena_id']!='default' or b['robot_id']!=self._robot_id:return 200,self._response(False)
        if not isinstance(b['request_id'],str) or not b['request_id']:return 400,self._response(False)
        if 'position' in b:
            p=b['position'];c=b['channel']
            if not isinstance(p,dict) or set(p)!={'x','y'}:return 400,self._response(False)
            if any(isinstance(p[k],bool) or not isinstance(p[k],(int,float)) or not math.isfinite(p[k]) or abs(p[k])>2000000 for k in ('x','y')):
                return 400,self._response(False)
            if isinstance(c,bool) or not isinstance(c,(int,float)) or not math.isfinite(c) or int(c)!=c or not 1<=c<=20:
                return 400,self._response(False)
        signature=(path,json.dumps(b,sort_keys=True,allow_nan=False))
        if b['request_id'] in self._cache:
            old,result=self._cache[b['request_id']]
            return copy.deepcopy(result) if signature==old else (409,self._response(False))
        if self._exited:raise ConnectionError('Self API closed')
        if self._start is not None and (time.monotonic()-self._start>=self._remaining or self._virtual_us>=360000000000):
            self._exited=True;raise ConnectionError('Self deadline expired')
        if (path=='/enter' and self._entered) or (path!='/enter' and not self._entered):return 200,self._response(False)
        if path=='/enter':
            self._entered=True;self._start=time.monotonic()
            response=self._response(True,max_virtual_duration_s=360000,max_real_duration_s=1200,
                                    remaining_real_duration_s=self._remaining)
        elif path=='/exit':
            self._exited=True;response=self._response(True,exit_reason='user_exit')
        else:
            p=(float(b['position']['x']),float(b['position']['y']));c=int(b['channel'])
            move=math.dist(self._position,p)/5;switch=float(path=='/measure' and c!=self._channel)
            parts=dict(movement_s=move,switch_s=switch,detection_s=0.,optical_s=0.,laser_s=0.)
            s=next((s for s in self._sources if s['channel']==c and c not in self._cleared),None)
            distance=math.inf if s is None else math.hypot(s['x']-p[0],s['y']-p[1])
            if path=='/measure':
                parts['detection_s']=5.;self._channel=c
                if s is None or distance>s['radius']:result=dict(measure_result='no_signal')
                elif distance<=5:result=dict(measure_result='near')
                else:result=dict(measure_result='direction',svd_deg=self._reading(p,s))
            else:
                parts['optical_s']=3.
                if distance<=20:
                    self._cleared.add(c);parts['laser_s']=2.;result=dict(clear_result='success')
                else:result=dict(clear_result='no_target_in_range')
            for k,v in parts.items():self._components[k]+=v
            self._virtual_us+=round(sum(parts.values())*1e6);self._position=p
            response=self._response(True,**result)
        result=(200,response);self._cache[b['request_id']]=(signature,copy.deepcopy(result));return result
    def evaluation(self):
        """Evaluator-only: never exposed by /enter, /measure, /clear, /exit."""
        return dict(total=len(self._sources),cleared=len(self._cleared),
                    remaining_channels=sorted(s['channel'] for s in self._sources if s['channel'] not in self._cleared),
                    components=self._components.copy(),virtual_time_s=self._virtual_us/1e6)
