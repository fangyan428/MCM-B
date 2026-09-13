"""Reproduce the three manuscript figures from analytic constraints and frozen data.
Backend: Python/matplotlib. No invented observations or excluded validation runs.
"""
from pathlib import Path
import sys, json, csv, math
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Circle
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from question4.geometry import radial_mesh
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Alibaba PuHuiTi','DejaVu Sans'],
 'font.size':9,'axes.labelsize':9,'axes.titlesize':10,'axes.spines.top':False,
 'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False,
 'legend.frameon':False,'axes.linewidth':0.7})
OUT=ROOT/'manuscript/figures';OUT.mkdir(exist_ok=True)
TEAL='#227D8D';GRAY='#C6D0D5';ORANGE='#B86535'

def save(fig,name):
    fig.canvas.draw()
    # All exports are single scientific panels; alignment is not applicable.
    (OUT/(name+'.alignment.json')).write_text(json.dumps({'status':'NOT APPLICABLE','panels':1}))
    fig.savefig(OUT/(name+'.pdf'),metadata={'Creator':'Python/matplotlib'},bbox_inches=None)
    fig.savefig(OUT/(name+'.svg'),metadata={'Creator':'Python/matplotlib'},bbox_inches=None)
    fig.savefig(OUT/(name+'.png'),dpi=300)
    plt.close(fig)

# Analytic region represented on a regular display grid; this is not a proof by sampling.
a,b=np.meshgrid(np.linspace(-40,1100,571),np.linspace(-1050,1050,701))
delta=np.deg2rad(1.005);h=a*np.cos(delta)-abs(b)*np.sin(delta);q2=a*a+b*b
reception=(a>=0)&(q2-10*h+25<=1000**2)&(q2<=2000*h)
cross=abs(b)*np.cos(delta)-a*np.sin(delta)
dmax=np.sqrt(np.maximum(q2+25-10*h,q2+1500**2-3000*h))
safe=reception&(cross>5)&(cross>=dmax*np.sin(np.deg2rad(20)))
z=np.where(safe,2,np.where(reception,1,0))
fig,ax=plt.subplots(figsize=(5.35,3.9));fig.subplots_adjust(left=.15,right=.95,bottom=.15,top=.9)
ax.pcolormesh(a,b,z,cmap=ListedColormap(['white','#E1E7EA',TEAL]),shading='auto',rasterized=True)
ax.axhline(0,color='#8A959B',linewidth=.65);ax.axvline(0,color='#8A959B',linewidth=.65)
ax.plot([0,1500],[0,1500*np.tan(delta)],color=ORANGE,lw=1)
ax.plot([0,1500],[0,-1500*np.tan(delta)],color=ORANGE,lw=1)
ax.scatter([800,800],[605,-605],c='#152F40',s=22,zorder=5)
ax.text(805,700,'(800, 605)',fontsize=8)
ax.text(805,-765,'(800, −605)',fontsize=8)
ax.text(180,795,'保证接收域',color='#44535F',fontsize=8)
ax.text(480,410,'候选域',color='white',fontsize=9)
ax.set(xlim=(-40,1100),ylim=(-1050,1050),xlabel='沿首次示向方向的位移 a (m)',ylabel='横向位移 b (m)')
ax.set_xticks([0,250,500,750,1000]);ax.set_yticks([-1000,-500,0,500,1000])
ax.set_aspect('equal',adjustable='box');save(fig,'q2_candidate')

# Layout-level pairing; all four error conditions are retained within every layout.
rows=list(csv.DictReader((ROOT/'question3/innovation/final_paired.csv').open()))
rows=[r for r in rows if r['rounding']=='bounded']
groups={}
for r in rows:
    parts=r['case_id'].split('_');seed=next(x for x in parts if x.isdigit())
    family=r['case_id'][len('final_'):r['case_id'].index('_'+seed)]
    groups.setdefault((family,seed),[]).append(r)
assert len(groups)==120 and all(len(v)==4 for v in groups.values())
fams=['uniform','outer','cluster','min_radius','radial','reception_edge']
labels=['均匀','外缘','聚集','最小半径','窄径向','接收边缘']
source=[]
fig,ax=plt.subplots(figsize=(6.3,3.1));fig.subplots_adjust(left=.13,right=.98,bottom=.19,top=.93)
for i,fam in enumerate(fams):
    vals=[]
    for (f,s),rr in sorted(groups.items()):
        if f!=fam:continue
        base=np.mean([float(r['baseline']) for r in rr]);cand=np.mean([float(r['candidate']) for r in rr])
        change=100*(cand/base-1);vals.append(change)
        source.append({'family':f,'seed':s,'error_conditions':4,'base_s':base,'candidate_s':cand,'layout_mean_change_pct':change})
    # Deterministic positions only; no random thinning or case selection.
    jitter=np.linspace(-.2,.2,len(vals))
    ax.scatter(i+jitter,vals,s=19,color=TEAL,alpha=.78,edgecolors='white',linewidth=.3)
    ax.plot([i-.25,i+.25],[np.median(vals)]*2,color='#182D3A',lw=1.5)
ax.axhline(0,color=ORANGE,ls='--',lw=.9)
ax.set_xticks(range(6),labels);ax.set_ylabel('布局平均总时间相对变化 (%)')
ax.set_ylim(-30,65);ax.set_xlim(-.55,5.55)
ax.grid(axis='y',color='#E5E9EC',lw=.5);ax.set_axisbelow(True)
ax.text(.01,1.015,'120个布局，每点合并4种误差；横线为类别中位数',transform=ax.transAxes,fontsize=8)
save(fig,'q3_performance')
with (OUT/'q3_layout_source.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(source[0]));w.writeheader();w.writerows(source)

# Exact station coordinates and triangulation used by the retained Q4 strategy.
pts,tri=radial_mesh();maxedge=max(np.linalg.norm(pts[t][:,None]-pts[t][None,:],axis=2).max() for t in tri)
assert len(pts)==25 and len(tri)==36 and maxedge<1000
fig,ax=plt.subplots(figsize=(4.5,3.75));fig.subplots_adjust(left=.17,right=.96,bottom=.16,top=.96)
ax.triplot(pts[:,0],pts[:,1],tri,color='#AABBC2',lw=.7,zorder=1)
ax.add_patch(Circle((0,0),1800,fill=False,edgecolor=ORANGE,ls='--',lw=1.2,zorder=3))
ax.scatter(pts[1:13,0],pts[1:13,1],s=19,color=TEAL,zorder=4)
ax.scatter(pts[13:,0],pts[13:,1],s=24,marker='s',color='#223D4A',zorder=4)
ax.scatter([0],[0],s=27,marker='D',color=ORANGE,zorder=5)
ax.set(xlim=(-2100,2100),ylim=(-2100,2100),xlabel='x (m)',ylabel='y (m)')
ax.set_xticks([-1800,-900,0,900,1800]);ax.set_yticks([-1800,-900,0,900,1800]);ax.set_aspect('equal')
save(fig,'q4_coverage')
(OUT/'geometry_source.json').write_text(json.dumps({'q2_error_deg':1.005,'q2_min_angle_deg':20,'q4_stations':pts.tolist(),'q4_triangles':tri.tolist(),'q4_max_edge_m':maxedge},indent=2))
print('Generated 3 figures; q3 layout change range',min(s['layout_mean_change_pct'] for s in source),max(s['layout_mean_change_pct'] for s in source))
