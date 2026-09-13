"""Draw the narrative manuscript figures from existing observations and analytic geometry.

Schematic coordinates illustrate logic; they are never presented as observed trajectories.
Statistical panels retain all paired cases in their stated batch. No simulations run here.
"""
from pathlib import Path
import csv, json, math, hashlib, re, os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mcm-draft-mpl')
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge, FancyBboxPatch
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / 'source_data'
OUT = ROOT / 'figures'
QA = ROOT / 'qa'
TEAL, DARK, ORANGE, GRAY = '#227D8D', '#213B4A', '#B65F35', '#BECBD0'
mpl.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Alibaba PuHuiTi','DejaVu Sans'],
    'font.size':10, 'axes.labelsize':10, 'axes.titlesize':10, 'axes.spines.top':False,
    'axes.spines.right':False, 'pdf.fonttype':42, 'svg.fonttype':'none',
    'axes.unicode_minus':False, 'legend.frameon':False, 'axes.linewidth':.7})
manifest = []

def canvas(height=3.7, left=.14, bottom=.18):
    fig, ax = plt.subplots(figsize=(6.8,height))
    fig.subplots_adjust(left=left,right=.96,bottom=bottom,top=.93)
    return fig,ax

def save(fig, name, claim, kind, source):
    fig.canvas.draw()
    (QA/(name+'.alignment.json')).write_text(json.dumps({'status':'NOT APPLICABLE','panels':1,'reason':'One scientific drawing area.'}))
    fig.savefig(OUT/(name+'.pdf'))
    fig.savefig(OUT/(name+'.svg'))
    fig.savefig(OUT/(name+'.png'),dpi=300)
    manifest.append(dict(id=name,claim=claim,kind=kind,source=source))
    plt.close(fig)

def box(ax,x,y,w,h,text,color=TEAL,fs=10):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.015,rounding_size=0.025',
        facecolor='#F2F6F7',edgecolor=color,lw=1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fs,color=DARK)

def arrow(ax,p,q):
    ax.annotate('',xy=q,xytext=p,arrowprops=dict(arrowstyle='->',color=DARK,lw=1.15))

# 1. The question chain and the shared observation/action loop.
fig,ax=canvas(3.2,.04,.05);ax.set(xlim=(0,10),ylim=(0,4));ax.axis('off')
for x,txt in [(0.15,'Q2：两次测向\n约束接收与交会几何'),(3.5,'Q3：整局时间\n联合观测、移动与清除'),(6.85,'Q4：定向失联\n重建发现与清除保证')]:
    box(ax,x,2.45,3,.95,txt)
arrow(ax,(3.2,2.92),(3.45,2.92));arrow(ax,(6.55,2.92),(6.8,2.92))
for x,txt in [(.15,'公开反馈'),(2.7,'更新可行集合'),(5.25,'检查行动证书'),(7.8,'执行并重排')]:
    box(ax,x,.6,2.05,.8,txt,GRAY)
for x in [2.25,4.8,7.35]:arrow(ax,(x,1),(x+.4,1))
ax.text(5,1.9,'共同底线：不删去真实位置；有依据才宣布任务完成',ha='center',color=DARK)
arrow(ax,(8.8,.55),(8.8,.2));ax.plot([1.15,8.8],[.2,.2],color=DARK,lw=1)
arrow(ax,(1.15,.2),(1.15,.55))
save(fig,'fig01_overview','三个问题逐步改变优化对象和信息条件','整体流程示意','model definitions')

# 2. An exact, measurement-compatible counterexample from the verified Q1 record.
fig,ax=canvas(3.4);t=np.array([[0,0],[20,0],[10,10*np.sqrt(3)]])
ax.add_patch(Polygon(t,facecolor='#DFEEF0',edgecolor=TEAL,lw=1.5))
ax.add_patch(Circle((10,0),10,fill=False,color=ORANGE,ls='--',lw=1.5))
ax.add_patch(Circle((10,10/np.sqrt(3)),20/np.sqrt(3),fill=False,color=DARK,lw=1))
ax.scatter(t[:,0],t[:,1],color=TEAL,s=28,zorder=5)
ax.text(23,15,'区域直径 D = 20 m',fontsize=10)
ax.text(23,10,'半径 D/2 的圆漏掉顶点',color=ORANGE)
ax.text(23,5,'最小覆盖半径 = 11.55 m',color=DARK)
ax.set(xlim=(-4,52),ylim=(-12,21),xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal')
save(fig,'fig02_diameter','区域直径的一半不是一般覆盖半径','严格几何反例','q12_verification.json: q1_triangle')

# 3. Concrete Q2 failures, in the same local coordinate system.
fig,ax=canvas(3.1);S=np.array([0,0]);G=np.array([1500,0]);side=np.array([0,500]);front=np.array([500,0])
ax.plot([0,1500],[0,0],color=TEAL,lw=2)
ax.plot([0,1500],[500,0],color=ORANGE,lw=1.5,ls='--')
ax.scatter([0,0,500,1500],[0,500,0,0],s=[30,35,35,45],c=[DARK,ORANGE,TEAL,DARK],zorder=4)
ax.text(60,525,'横移点 (0,500)：距离源 1581.14 m，失联',color=ORANGE)
ax.text(500,-170,'前移点 (500,0)：中心线重合，交会退化',ha='center',color=TEAL)
ax.text(1470,100,'源 (1500,0)',ha='right');ax.text(20,100,'首测点 S')
ax.text(900,410,'此例接收半径为 1500 m',ha='center',fontsize=9)
ax.set(xlim=(-80,1650),ylim=(-250,720),xlabel='沿首次示向方向 (m)',ylabel='横向位置 (m)')
save(fig,'fig03_q2_failures','横移可能失联，沿示向前进可能退化','构造反例','Q2 documented counterexamples')

# 4. Exact inequalities visualized on a display grid, not a grid proof.
a,b=np.meshgrid(np.linspace(-40,1100,571),np.linspace(-1050,1050,701))
d=np.deg2rad(1.005);h=a*np.cos(d)-abs(b)*np.sin(d);q2=a*a+b*b
rec=(a>=0)&(q2-10*h+25<=1e6)&(q2<=2000*h)
c=abs(b)*np.cos(d)-a*np.sin(d)
M=np.sqrt(np.maximum(q2+25-10*h,q2+1500**2-3000*h))
safe=rec&(c>5)&(c>=M*np.sin(np.deg2rad(20)))
fig,ax=canvas(4.1)
ax.pcolormesh(a,b,np.where(safe,2,np.where(rec,1,0)),cmap=ListedColormap(['white','#DFE5E8',TEAL]),shading='auto',rasterized=True)
ax.axhline(0,color=GRAY,lw=.8)
ax.scatter([800,800],[605,-605],c=DARK,s=28,zorder=5)
ax.text(825,900,'(800,605)',fontsize=9);ax.text(825,-980,'(800,−605)',fontsize=9)
ax.text(480,120,'保证接收域',fontsize=9,ha='center');ax.text(530,500,'安全候选域',color='white',fontsize=9,ha='center')
ax.set(xlim=(-40,1100),ylim=(-1050,1050),xlabel='前向位移 a (m)',ylabel='横向位移 b (m)');ax.set_aspect('equal')
save(fig,'fig04_q2_region','两侧候选兼顾接收与非退化交会','解析条件显示','Q2 reception and safe-region inequalities')

# 5. Keep all eight archived candidates; mirror points have identical metrics.
q12=json.loads((DATA/'q12_verification.json').read_text())
rows=q12['q2_fixed_library_1_005deg']['rows']
fig,ax=canvas(3.5)
nd=sorted([r for r in rows if r['pareto_within_fixed_library']],key=lambda r:r['move_and_measure_s'])
ax.plot([r['move_and_measure_s'] for r in nd],[r['dense_sample_worst_D'] for r in nd],color=TEAL,lw=1)
offsets={(400,500):(-8,-23),(500,400):(8,4),(500,500):(-54,-16),(600,400):(8,5),(700,450):(-60,-18),(750,400):(7,5),(800,605):(-73,-15),(850,450):(-76,6)}
for r in rows:
    xy=(r['move_and_measure_s'],r['dense_sample_worst_D']);key=tuple(r['offset'])
    ax.scatter(*xy,color=TEAL if r['pareto_within_fixed_library'] else GRAY,s=32,zorder=3)
    ax.annotate(str(key),xy,xytext=offsets[key],textcoords='offset points',fontsize=8)
ax.set(xlim=(126,214),ylim=(112,319),xlabel='移动与第二次检测时间 (s)',ylabel='采样最大定位直径 (m)')
ax.set_axisbelow(True)
save(fig,'fig05_q2_tradeoff','更小的定位直径需要支付移动代价','有限场景数值结果','q12_verification.json: all eight fixed-library offsets')

# 6. Algorithmic decision schematic, no claimed sample trajectory.
fig,ax=canvas(4.1,.03,.04);ax.set(xlim=(0,10),ylim=(0,6));ax.axis('off')
box(ax,.2,4.8,2.8,.8,'保留各频道可行集合')
box(ax,3.6,4.8,2.8,.8,'搜索站 + 已知源任务')
box(ax,7,4.8,2.8,.8,'滚动规划，只执行首项')
arrow(ax,(3.05,5.2),(3.55,5.2));arrow(ax,(6.45,5.2),(6.95,5.2))
box(ax,.2,2.9,2.8,.85,'整个集合可被20 m圆覆盖？')
box(ax,3.6,2.9,2.8,.85,'首次横向视差\n后续中心测量',fs=9)
box(ax,7,2.9,2.8,.85,'筛选其他频道\n仅有足够价值时观测',fs=9)
arrow(ax,(8.4,4.75),(8.4,4.1));ax.plot([1.6,8.4],[4.1,4.1],color=DARK,lw=1)
arrow(ax,(1.6,4.1),(1.6,3.8));arrow(ax,(3.05,3.33),(3.55,3.33))
ax.text(3.3,3.58,'否',ha='center',fontsize=9)
arrow(ax,(6.45,3.33),(6.95,3.33))
box(ax,.2,.8,2.8,.9,'清除；记录成功频道')
box(ax,3.6,.8,2.8,.9,'依据真实反馈更新\n完成任务后重排',fs=9)
box(ax,7,.8,2.8,.9,'仅满足覆盖或计数证书\n且无待清源时退出',fs=9)
arrow(ax,(1.6,2.85),(1.6,1.75));ax.text(1.85,2.25,'是',fontsize=9)
arrow(ax,(8.4,2.85),(8.4,2.25));arrow(ax,(8.4,2.25),(5,2.25));arrow(ax,(5,2.25),(5,1.75))
arrow(ax,(3.05,1.25),(3.55,1.25));arrow(ax,(6.45,1.25),(6.95,1.25))
save(fig,'fig06_q3_algorithm','定位动作与任务调度共享同一个状态','算法示意图','Q3 implementation logic; finite fallback described in text')

# 7. Omnidirectional seven-station discovery coverage.
angs=np.arange(6)*np.pi/3
seven=np.vstack([[0,0],1125*np.c_[np.cos(angs),np.sin(angs)]])
fig,ax=canvas(4)
for s in seven:ax.add_patch(Circle(s,1000,fill=False,color=GRAY,lw=.8))
ax.add_patch(Circle((0,0),1800,fill=False,color=ORANGE,lw=1.5))
ax.scatter(seven[:,0],seven[:,1],color=TEAL,s=26,zorder=4)
g=1800*np.array([np.cos(np.pi/6),np.sin(np.pi/6)])
ax.plot([seven[1,0],g[0]],[seven[1,1],g[1]],color=DARK,lw=1.3)
ax.scatter(*g,color=ORANGE,s=30,zorder=5)
ax.text(-2050,2250,'全域最远近站距离约 999.11 m < 1000 m',fontsize=9)
ax.set(xlim=(-2250,2250),ylim=(-2250,2480),xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal')
save(fig,'fig07_q3_cover','七站圆盘覆盖支撑全向源的未知频道停止判据','解析构造','Q3 seven-station geometry')

# 8. Directional no-signal failure: source at origin, outward half-plane to the right.
fig,ax=canvas(3.5)
ax.add_patch(Wedge((0,0),1000,-90,90,facecolor='#DFEEF0',edgecolor=TEAL,lw=1.1))
ax.add_patch(Circle((0,0),1000,fill=False,color=GRAY,ls='--'))
ax.axvline(0,color=TEAL,lw=.8)
ax.scatter([0,-350,650],[0,0,250],color=[DARK,ORANGE,TEAL],s=35,zorder=4)
ax.text(-750,170,'背面站',color=ORANGE)
ax.text(.5,1.035,'背面站距离350 m仍无信号；正面站可接收',transform=ax.transAxes,ha='center',fontsize=9)
ax.text(100,-550,'发射半平面',color=TEAL,fontsize=9)
ax.text(220,400,'正面站',color=TEAL)
ax.text(40,-110,'源');ax.set(xlim=(-1150,1150),ylim=(-1080,1100),xlabel='相对源的 x (m)',ylabel='相对源的 y (m)');ax.set_aspect('equal')
save(fig,'fig08_no_signal','定向无信号不能排除近处仍有源','构造反例示意','directional reception model, R=1000 m')

# 9. Exact 25-station construction, without a dependency on the optimizer.
a0=np.arange(12)*np.pi/6
pts=np.vstack([[0,0],950*np.c_[np.cos(a0),np.sin(a0)],1870*np.c_[np.cos(a0+np.pi/12),np.sin(a0+np.pi/12)]])
tri=[]
for k in range(12):
    tri.extend([[0,1+k,1+(k+1)%12],[1+k,1+(k+1)%12,13+k],[1+k,13+(k-1)%12,13+k]])
tri=np.array(tri);maxedge=max(np.linalg.norm(pts[t][:,None]-pts[t][None,:],axis=2).max() for t in tri)
assert maxedge<1000 and 1870*np.cos(np.pi/12)>1800
fig,ax=canvas(4)
ax.triplot(pts[:,0],pts[:,1],tri,color=GRAY,lw=.8)
ax.add_patch(Circle((0,0),1800,fill=False,color=ORANGE,ls='--',lw=1.25))
ax.scatter(pts[:,0],pts[:,1],color=TEAL,s=23,zorder=4)
ax.add_patch(Polygon(pts[tri[4]],facecolor='#DFEEF0',edgecolor=TEAL,lw=1.6))
ax.text(-2050,2110,'36个三角形；最长边983.60 m；外包内切半径1806.28 m',fontsize=8)
ax.set(xlim=(-2150,2150),ylim=(-2050,2350),xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal')
save(fig,'fig09_q4_cover','近距三角形顶点覆盖任意发射半平面','连续覆盖解析构造','25-station analytic coordinates and triangles')

# 10. Local portion of finite optical covering; units and scale are exact.
fig,ax=canvas(3.2)
for x in [0,28,56,84]:ax.plot([x,x],[0,56],color=GRAY,lw=.8)
for y in [0,28,56]:ax.plot([0,84],[y,y],color=GRAY,lw=.8)
centers=np.array([[14,14],[42,14],[70,14],[70,42],[42,42],[14,42]])
ax.plot(centers[:,0],centers[:,1],color=TEAL,lw=1.1)
ax.scatter(centers[:,0],centers[:,1],color=TEAL,s=20)
ax.add_patch(Circle((42,14),20,fill=False,color=ORANGE,lw=1.3))
ax.plot([42,56],[14,28],color=ORANGE,ls='--')
ax.text(94,40,'格边长 ≤ 28 m')
ax.text(94,26,'半对角线 ≤ 19.80 m')
ax.text(94,12,'清除半径：20 m',color=ORANGE)
ax.set(xlim=(-5,155),ylim=(-9,65),xlabel='沿首次示向方向 (m)',ylabel='横向位置 (m)');ax.set_aspect('equal')
save(fig,'fig10_optical','光学有限覆盖不依赖是否还能接收无线电信号','算法几何示意','28 m grid and 20 m clearance radius; local excerpt')

# 11. Layout-paired Q3 outcomes: every one of the 120 layouts is present.
pairs=list(csv.DictReader((DATA/'q3_final_pairs.csv').open()))
groups={}
for r in pairs:
    if r['rounding']!='bounded':continue
    m=re.fullmatch(r'final_(.+)_(\d+)_(.+)',r['case_id'])
    groups.setdefault((m[1],m[2]),[]).append(r)
assert len(groups)==120 and all(len(v)==4 for v in groups.values())
fams=['uniform','outer','cluster','min_radius','radial','reception_edge']
labels=['均匀','外缘','聚集','最小半径','窄径向','接收边缘']
fig,ax=canvas(3.5)
layout_data=[]
for i,f in enumerate(fams):
    vals=[]
    for (fam,seed),rr in sorted(groups.items()):
        if fam!=f:continue
        base=np.mean([float(r['baseline_s']) for r in rr]);cand=np.mean([float(r['candidate_s']) for r in rr])
        val=100*(cand/base-1);vals.append(val)
        layout_data.append(dict(family=f,seed=seed,base_s=base,candidate_s=cand,change_pct=val))
    ax.scatter(i+np.linspace(-.20,.20,len(vals)),vals,s=22,color=TEAL,alpha=.8)
    ax.plot([i-.25,i+.25],[np.median(vals)]*2,color=DARK,lw=1.6)
ax.axhline(0,color=ORANGE,ls='--',lw=1)
ax.set(xticks=range(6),xticklabels=labels,ylabel='布局平均总时间变化 (%)',ylim=(-30,68),xlim=(-.5,5.5))
ax.text(.01,1.025,'120个布局；每点合并4种误差；短线为组内中位数',transform=ax.transAxes,fontsize=9)
save(fig,'fig11_q3_distribution','平均收益不意味着每个布局都变快','配对统计图','q3_final_pairs.csv: all 480 bounded runs, aggregated to 120 layouts')

# 12. Exact action-cost mean differences.
cost=list(csv.DictReader((DATA/'q3_cost_components.csv').open()))
comp=['movement_s','detection_s','switch_s','optical_s','laser_s'];cn=['移动','检测','切频','光学','成功清除附加']
dif=[]
for k in comp:
    dct={r['variant']:float(r['mean_s']) for r in cost if r['rounding']=='bounded' and r['component']==k}
    dif.append(dct['GATED_TOUR_MULTI_PARALLAX']-dct['BASE'])
fig,ax=canvas(3.1,.18)
y=np.arange(6);vals=dif+[sum(dif)]
ax.barh(y,vals,color=[TEAL if v<0 else ORANGE for v in vals],height=.55)
ax.axvline(0,color=DARK,lw=.8)
for yi,v in zip(y,vals):ax.text(v+(-7 if v<0 else 7),yi,f'{v:+.2f}',ha='right' if v<0 else 'left',va='center',fontsize=9)
ax.set(yticks=y,yticklabels=cn+['合计'],xlabel='联合方案 − 基线：每局平均时间 (s)',xlim=(-485,120));ax.invert_yaxis()
save(fig,'fig12_q3_cost','更多检测换取更少移动，净节省341.33秒','动作代价分解','q3_cost_components.csv: bounded, 480 paired runs per arm')

# 13. Equal-layout final ablations share one parent; do not add their deltas.
stats=list(csv.DictReader((DATA/'q3_final_statistics.csv').open()))
lookup={r['variant']:float(r['mean']) for r in stats if r['rounding']=='bounded'}
parent='GATED_TOUR_SHARED_PARALLAX'
variants=['GATED_TOUR_MULTI_PARALLAX','GATED_NEAREST_SHARED_PARALLAX','GATED_TOUR_SHARED','TOUR_SHARED_PARALLAX']
names=['删除目标原地再观测','删除完整行程规划','删除首次视差','删除共享信息门控']
delta=[lookup[v]-lookup[parent] for v in variants]
fig,ax=canvas(3.0,.30)
ax.barh(range(4),delta,color=[TEAL if x<0 else ORANGE for x in delta],height=.5)
for i,v in enumerate(delta):ax.text(v+(-5 if v<0 else 5),i,f'{v:+.2f}',va='center',ha='right' if v<0 else 'left',fontsize=9)
ax.axvline(0,color=DARK,lw=.8)
ax.set(yticks=range(4),yticklabels=names,xlabel='相对共同父方案的平均时间变化 (s)',xlim=(-85,300));ax.invert_yaxis()
ax.text(.01,1.035,'共同父方案均值 3007.19 s；同一480次配对运行',transform=ax.transAxes,fontsize=9)
save(fig,'fig13_q3_ablation','视差、任务行程与观测筛选的贡献必须按共同父方案解释','配对消融均值图','q3_final_statistics.csv: bounded, four prespecified ablations')

# 14. Historical Q4 retained-scheme comparisons on both separate validation batches.
q4=list(csv.DictReader((DATA/'q4_source_data.csv').open()))
fig,ax=canvas(3.5,.24)
configs=['BASE','FINAL','COMPACT22','NO_CENTROID','NO_INFO']
names=['31站初始基线','25站推荐','改为22站','移除重心排序','移除信息删减']
historical=[]
for j,batch in enumerate(['round9_main','round9_rounding']):
    values=[]
    for cf in configs:
        rr=[r for r in q4 if r['batch']==batch and r['config']==cf];assert len(rr)==96
        v=float(np.mean([float(r['virtual_time_s']) for r in rr]));values.append(v)
        historical.append(dict(batch=batch,config=cf,runs=96,mean_s=v))
    ax.plot(values,np.arange(5)+(j-.5)*.18,marker='o' if j==0 else 's',lw=0,color=TEAL if j==0 else ORANGE,
        label='读数包络：96布局' if j==0 else '舍入压力：另96布局',markersize=5)
ax.set(yticks=range(5),yticklabels=names,xlabel='整局虚拟时间均值 (s)',xlim=(0,13500));ax.invert_yaxis()
ax.legend(loc='lower right',fontsize=8);ax.set_axisbelow(True)
save(fig,'fig14_q4_historical','25站布局与调度组合的收益，不能仅归因于站数减少','两批自建验证均值图','q4_source_data.csv: all 960 historical rows; 96 layouts per batch per arm')

# 15. Latest candidate paired layout differences; full distribution plus primary CI.
latest=[r for r in q4 if r['batch']=='reset_final_validation']
cfgs=['HIST_ADAPT','COVER_EXCHANGE','COVER_ELASTIC','COVER_EXCHANGE_ELASTIC']
base_by={r['case_id']:float(r['virtual_time_s']) for r in latest if r['config']=='BASE25'}
assert len(base_by)==960
fig,ax=canvas(3.7,.14,.23)
latest_layout=[]
for i,cf in enumerate(cfgs):
    gg={}
    for r in latest:
        if r['config']==cf:gg.setdefault(r['layout_id'],[]).append(r)
    assert len(gg)==120 and all(len(v)==8 for v in gg.values())
    vv=[]
    for layout,rr in sorted(gg.items()):
        b0=np.mean([base_by[r['case_id']] for r in rr]);v=np.mean([float(r['virtual_time_s']) for r in rr]);chg=100*(v/b0-1);vv.append(chg)
        latest_layout.append(dict(config=cf,layout=layout,change_pct=chg))
    ax.scatter(i+np.linspace(-.23,.23,len(vv)),vv,s=9,color=TEAL,alpha=.52)
    overall=100*(np.mean([float(r['virtual_time_s']) for r in latest if r['config']==cf])/np.mean(list(base_by.values()))-1)
    ax.scatter([i],[overall],marker='D',s=33,color=DARK,zorder=5)
ax.axhline(0,color=ORANGE,ls='--',lw=1)
ax.set(xticks=range(4),xticklabels=['历史自适应定位','仅动态替站','仅测站移动','替站＋移动'],ylabel='布局平均总时间变化 (%)',xlim=(-.6,3.6))
ax.text(.01,1.035,'每组120布局；小点为布局变化，菱形为整批均值之比的变化',transform=ax.transAxes,fontsize=8)
ax.text(.5,-.26,'组合省时0.366%；95%区间 [−0.183%, 0.921%]（省时为正）',transform=ax.transAxes,ha='center',fontsize=9,color=DARK)
save(fig,'fig15_q4_latest','动态覆盖可行，但未证明足以替换成熟方案的整局收益','配对统计与负结果图','q4_source_data.csv: all latest 4800 runs; primary CI from frozen statistics')

def writecsv(name,rr):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
writecsv('q3_layout_source.csv',layout_data);writecsv('q4_historical_source.csv',historical);writecsv('q4_latest_layout_source.csv',latest_layout)
(OUT/'figure_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT/'geometry_source.json').write_text(json.dumps({'stations':pts.tolist(),'triangles':tri.tolist(),'max_edge_m':maxedge},indent=2))
inputs=['q12_verification.json','q3_final_pairs.csv','q3_cost_components.csv','q3_final_statistics.csv','q4_source_data.csv']
(QA/'source_hashes.json').write_text(json.dumps({s:hashlib.sha256((DATA/s).read_bytes()).hexdigest() for s in inputs},indent=2))
print('Generated',len(manifest),'figures; Q3 cost delta',sum(dif),'s; 25-station max edge',maxedge)
