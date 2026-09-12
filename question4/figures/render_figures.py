import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];out=root/'figures';out.mkdir(exist_ok=True)
review=json.loads((root/'results/round9_review.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axs=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
for ax,(batch,title) in zip(axs,[('round9_main','Bounded readings · 96 fresh layouts'),('round9_rounding','Rounding stress · 96 fresh layouts')]):
 d=review[batch]['vs_baseline'];s=d['FINAL'];v=[d['BASE']['mean_s'],s['mean_s']]
 bars=ax.bar(['Initial baseline','Final: 25 stations'],v,color=['#a7b3bd','#087d77'],width=.57)
 for b,y in zip(bars,v):ax.text(b.get_x()+b.get_width()/2,y+180,f'{y:,.1f} s',ha='center',weight='bold')
 ax.set(ylim=(0,13500),ylabel='Mean total virtual time (s)',title=title)
 ax.text(.5,.89,f"{s['gain_pct']:.2f}% lower",transform=ax.transAxes,ha='center',color='#087d77',fontsize=17,weight='bold')
 ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig.suptitle('Complete clearance in every final-validation run',fontsize=15,weight='bold')
for ext in ['png','svg']:fig.savefig(out/f'final_total_time.{ext}',dpi=180)
plt.close(fig)
fig,ax=plt.subplots(figsize=(9.5,5),layout='constrained')
names=['RELOCATE','PROBE','REFINE','COST'];labels=['Route insertion','Centroid probe','Extra bearing refinement','Detection-cost routing']
for off,(batch,label,color) in zip([-.12,.12],[('round9_main','Bounded','#087d77'),('round9_rounding','Rounding stress','#d18432')]):
 stats=[review[batch]['vs_final'][n] for n in names];g=np.array([s['gain_pct'] for s in stats]);ci=np.array([s['bootstrap95_pct'] for s in stats])
 ax.errorbar(g,np.arange(4)+off,xerr=np.vstack([g-ci[:,0],ci[:,1]-g]),fmt='o',capsize=4,label=label,color=color)
ax.set_yticks(range(4),labels);ax.set_ylim(3.5,-.75);ax.axvline(0,color='#506273',lw=1);ax.axvline(1,color='#d18432',lw=1,ls='--')
ax.set(xlabel='Additional gain vs final configuration (%) · positive is faster',title='Stopping evidence: new mechanisms add less than about 1%')
ax.grid(axis='x',alpha=.2);ax.legend(loc='lower right');ax.text(.99,.98,'Paired bootstrap 95% intervals; 96 layouts per batch',transform=ax.transAxes,ha='right',va='top',fontsize=9)
for ext in ['png','svg']:fig.savefig(out/f'stopping_evidence.{ext}',dpi=180)
plt.close(fig)
# Geometry figure with public points only; use saved certificate to avoid strategy imports.
s=json.loads((root/'results/round9_main/FINAL/uniform_111000_spatial_hash/result.json').read_text())['stop_certificate']
p=np.array(s['stations']);t=np.array(s['triangles'])
fig,ax=plt.subplots(figsize=(6.5,6.5),layout='constrained')
ax.add_patch(plt.Circle((0,0),1800,color='#dcefeb',zorder=0));ax.triplot(p[:,0],p[:,1],t,color='#7b9da6',lw=.9,zorder=1)
ax.scatter(p[:,0],p[:,1],s=28,color='#087d77',zorder=3)
a=np.linspace(0,2*np.pi,500);ax.plot(1800*np.cos(a),1800*np.sin(a),color='#215268',lw=1.5,label='Target domain: radius 1,800 m')
ax.set(aspect='equal',xlabel='East (m)',ylabel='North (m)',title='25-station direction-independent search cover')
ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),fontsize=9);ax.grid(alpha=.12)
for ext in ['png','svg']:fig.savefig(out/f'directional_cover.{ext}',dpi=180)
plt.close(fig)
