"""Conservative second-bearing design. Local x axis = first measured bearing.
Run python question2/strategy.py. Requires numpy; scipy only for tests via Q1.
Numerical minimax search is sampled, NOT a certificate of continuous optimality.
"""
import json
from pathlib import Path
import numpy as np

DELTA = np.deg2rad(1.)

def candidate(q, min_angle_deg=20., error_deg=1.):
    """Analytic sufficient certificate, not a sampled feasibility test.

    error_deg also applies to reception geometry (not only intersection width).
    Physical ranges are the problem's fixed 5/1000/1500 metres.
    """
    a,b = np.asarray(q, float)
    if not np.isfinite([a,b,error_deg]).all() or not 0 < min_angle_deg < 90 or not 0 < error_deg < 45:
        return False
    if a < 0: return False
    delta = np.deg2rad(error_deg)
    h = a*np.cos(delta)-abs(b)*np.sin(delta)
    norm2=a*a+b*b
    reception = norm2-10*h+25 <= 1000**2+1e-8 and norm2 <= 2000*h+1e-8
    cross_lower=abs(b)*np.cos(delta)-a*np.sin(delta)
    max_distance=np.sqrt(max(norm2+25-10*h, norm2+1500**2-3000*h))
    return bool(reception and cross_lower > 5 and cross_lower >= max_distance*np.sin(np.deg2rad(min_angle_deg)))


def to_world(q, first_position=(0,0), bearing_deg=0):
    angle=np.deg2rad(bearing_deg)
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    return np.asarray(first_position)+rotation@np.asarray(q)


def scenarios(nr=51, na=5, ne=5):
    r,alpha,error=np.meshgrid(np.linspace(5.001,1500,nr),np.linspace(-DELTA,DELTA,na),
                              np.linspace(-DELTA,DELTA,ne),indexing='ij')
    g=np.column_stack([(r*np.cos(alpha)).ravel(),(r*np.sin(alpha)).ravel()])
    return g,error.ravel()


def diameters(q,g,error):
    """Exact four-half-plane vertex diameter for every scenario, in float arithmetic.
    Requires geometry in candidate(), which guarantees bounded intersections.
    """
    q=np.asarray(q,float)
    theta=np.arctan2(g[:,1]-q[1],g[:,0]-q[0])+error
    count=len(g)
    A=np.empty((count,4,2))
    A[:,0]=[np.sin(-DELTA),-np.cos(-DELTA)]
    A[:,1]=[-np.sin(DELTA),np.cos(DELTA)]
    A[:,2,0]=np.sin(theta-DELTA); A[:,2,1]=-np.cos(theta-DELTA)
    A[:,3,0]=-np.sin(theta+DELTA); A[:,3,1]=np.cos(theta+DELTA)
    rhs=np.zeros((count,4));rhs[:,2:]=A[:,2:]@q
    points=[];valid=[]
    for i in range(4):
        for j in range(i+1,4):
            det=A[:,i,0]*A[:,j,1]-A[:,i,1]*A[:,j,0]
            safe=np.abs(det)>1e-12
            den=np.where(safe,det,1)
            p=np.column_stack([(rhs[:,i]*A[:,j,1]-A[:,i,1]*rhs[:,j])/den,
                               (A[:,i,0]*rhs[:,j]-rhs[:,i]*A[:,j,0])/den])
            ok=safe & np.all(np.einsum('nij,nj->ni',A,p)<=rhs+1e-7,axis=1)
            points.append(p);valid.append(ok)
    v=np.stack(points,axis=1);ok=np.stack(valid,axis=1)
    if np.any(ok.sum(axis=1)<2): raise RuntimeError('Degenerate scenario outside solver assumptions')
    max2=np.zeros(count)
    for i in range(6):
        for j in range(i+1,6):
            d2=np.sum((v[:,i]-v[:,j])**2,axis=1)
            max2=np.maximum(max2,np.where(ok[:,i]&ok[:,j],d2,0))
    return np.sqrt(max2)


def search():
    g,e=scenarios()
    best=None;tested=0
    # Reflection symmetry: search upper component, reflect for second recommendation.
    for step,arange,brange in [(50,np.arange(0,1001,50),np.arange(50,1001,50)),]:
        for a in arange:
            for b in brange:
                if not candidate([a,b]):continue
                score=float(diameters([a,b],g,e).max());tested+=1
                row=(score,float(np.hypot(a,b)),float(a),float(b))
                if best is None or row<best:best=row
    _,_,a0,b0=best
    for a in np.arange(max(0,a0-50),a0+51,5):
        for b in np.arange(max(5,b0-50),b0+51,5):
            if not candidate([a,b]):continue
            score=float(diameters([a,b],g,e).max());tested+=1
            row=(score,float(np.hypot(a,b)),float(a),float(b))
            if row<best:best=row
    return best,tested


def main():
    best,tested=search();score,distance,a,b=best
    g,e=scenarios(301,11,11)
    rows=[]
    for name,q in [('recommended',[a,b]),('balanced',[500,500]),('forward_biased',[750,400])]:
        if not candidate(q):continue
        d=diameters(q,g,e);k=int(d.argmax())
        rows.append(dict(name=name,local_point=q,move_distance=float(np.linalg.norm(q)),
                         move_and_detection_seconds=float(np.linalg.norm(q)/5+5),
                         sampled_worst_diameter=float(d[k]),worst_source=g[k].tolist(),
                         worst_second_error_deg=float(np.rad2deg(e[k]))))
    result=dict(parameters=dict(error_deg=1,min_angle_deg=20,initial_range=[5,1500]),
                search_scenarios=51*5*5,candidates_evaluated=tested,
                validation_scenarios=len(g),recommendation=[a,b],mirror=[a,-b],
                sampled_search_worst=score,comparisons=rows,
                caveat='Sampled minimax on a conservative full-sector candidate region; not continuous global optimum.')
    Path(__file__).with_name('results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
