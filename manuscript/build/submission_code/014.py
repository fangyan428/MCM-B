"""Revision: source-grounded geometry, conceptual routes, and complete distributions."""
exec((__import__('pathlib').Path(__file__).with_name('make_figures.py')).read_text())
import sys
sys.path.insert(0,'USER_HOME/.codex/skills/nature-figure/scripts')
from audit_panel_alignment import require_matplotlib_panel_alignment
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Alibaba PuHuiTi','DejaVu Sans'],'pdf.fonttype':42,'svg.fonttype':'none'})
PURPLE='#8564A9'; RED='#B94145'; GREEN='#3E8864'; LIGHT='#DFEEF0'
oldsave=save
def save(fig,name,claim,kind,source):
    if len(fig.axes)>1:
        require_matplotlib_panel_alignment(fig,json_out=QA/(name+'.alignment.json'),require_panel_labels=False)
        fig.savefig(OUT/(name+'.pdf'))
        fig.savefig(OUT/(name+'.svg'))
        fig.savefig(OUT/(name+'.png'),dpi=300)
        plt.close(fig)
    else:oldsave(fig,name,claim,kind,source)
def multi(n,height=3.0):
    f,aa=plt.subplots(1,n,figsize=(6.8,height));f.subplots_adjust(left=.145,right=.98,bottom=.20,top=.85,wspace=.42)
    return f,aa

def clip(poly,normal,bound):
    result=[]
    for p,q in zip(poly,np.roll(poly,-1,axis=0)):
        vp=normal@p-bound;vq=normal@q-bound
        if vp<=1e-9:result.append(p)
        if (vp<0 and vq>0) or (vp>0 and vq<0):result.append(p+(q-p)*vp/(vp-vq))
    return np.array(result)
def observe(poly,s,g,delta=1):
    theta=np.arctan2(*(g-s)[::-1]);d=np.deg2rad(delta)
    lo=np.array([np.cos(theta-d),np.sin(theta-d)]);hi=np.array([np.cos(theta+d),np.sin(theta+d)])
    for norm in [np.array([lo[1],-lo[0]]),np.array([-hi[1],hi[0]])]:poly=clip(poly,norm,norm@s)
    return poly

# Three explicit layers and an observation feedback loop.
f,ax=canvas(3.9,.025,.04);ax.set(xlim=(0,10),ylim=(0,6));ax.axis('off')
for y,label in [(4.8,'定位层'),(2.8,'搜索层'),(.8,'调度层')]:ax.text(.1,y+.35,label,va='center',weight='bold',fontsize=9)
for x,txt in [(1.35,'测向读数'),(3.5,'误差扇区'),(5.65,'候选区域'),(7.8,'第二点选择')]:box(ax,x,4.8,1.85,.75,txt,fs=9)
for x in [3.23,5.38,7.53]:arrow(ax,(x,5.17),(x+.2,5.17))
for x,txt in [(1.35,'多站覆盖\n发现未知源'),(4.5,'重复观测\n收缩位置区域'),(7.65,'覆盖检查\n光学清除')]:box(ax,x,2.6,2,.95,txt,fs=9)
arrow(ax,(3.4,3.05),(4.45,3.05));arrow(ax,(6.55,3.05),(7.6,3.05))
arrow(ax,(8.7,4.75),(8.7,4.15));arrow(ax,(8.7,4.15),(5.5,4.15));arrow(ax,(5.5,4.15),(5.5,3.6))
box(ax,1.35,.45,3.7,1.05,'搜索与清除任务进入同一任务池\n仅执行首项，收到反馈后重排',fs=9)
box(ax,6.05,.45,3.6,1.05,'已知源清完 + 覆盖或数量证书\n满足才退出，否则继续',fs=9)
arrow(ax,(5.1,.98),(6,.98));arrow(ax,(3.2,1.55),(3.2,2.2));arrow(ax,(3.2,2.2),(2.35,2.2));arrow(ax,(2.35,2.2),(2.35,2.55))
save(f,'fig01_overview','定位、搜索和调度形成反馈闭环','整体流程图','model definitions')

# Diameter below40 is insufficient for a20m clearance disk.
f,ax=canvas(3.3);D=39.;t=np.array([[0,0],[D,0],[D/2,D*np.sqrt(3)/2]])
ax.add_patch(Polygon(t,facecolor='#EBE4F1',edgecolor=PURPLE,lw=1.5))
ax.plot([0,D],[0,0],color=DARK,lw=2)
ax.add_patch(Circle((D/2,0),D/2,fill=False,color=ORANGE,ls='--',lw=1.4))
ax.add_patch(Circle((D/2,D/(2*np.sqrt(3))),D/np.sqrt(3),fill=False,color=TEAL,lw=1.3))
ax.scatter(*t[2],color=RED,s=30,zorder=5)
for y,txt,c in [(28,'D = 39 m < 40 m',DARK),(16,'D/2 = 19.50 m：漏顶点',ORANGE),(4,'最小覆盖半径 = 22.52 m',TEAL),(-8,'大于 20 m 清除半径',RED)]:ax.text(47,y,txt,color=c,fontsize=9)
ax.set(xlim=(-5,105),ylim=(-23,40),xlabel='x (m)',ylabel='y (m)',aspect='equal')
save(f,'fig02_diameter','直径小于40m仍不能保证一次20m清除','合法测向几何反例','D=39 equilateral construction, Appendix A.1')

# Bearing intersection, exact polygons, with a zoom rather than exaggerated angles.
g=np.array([600.,180.]);sites=[np.array([0.,0.]),np.array([850.,-450.])]
p=np.array([[-1800.,-1800.],[1800.,-1800.],[1800.,1800.],[-1800.,1800.]])
for s in sites:p=observe(p,s,g)
dist=np.linalg.norm(p[:,None]-p[None,:],axis=2);i,j=np.unravel_index(np.argmax(dist),dist.shape)
f,aa=multi(2,3.5)
for ax in aa:
    for k,s in enumerate(sites):
        theta=np.arctan2(*(g-s)[::-1]);color=TEAL if k==0 else ORANGE
        for delta in [-1,0,1]:
            end=s+1600*np.array([np.cos(theta+np.deg2rad(delta)),np.sin(theta+np.deg2rad(delta))])
            ax.plot([s[0],end[0]],[s[1],end[1]],color=color,lw=.8,ls='--' if delta else '-')
    ax.add_patch(Polygon(p,facecolor='#EBE4F1',edgecolor=PURPLE,lw=1.2,zorder=4))
    ax.plot(p[[i,j],0],p[[i,j],1],color=DARK,lw=1.7,zorder=5)
    ax.set(xlabel='x (m)',ylabel='y (m)',aspect='equal')
aa[0].scatter(np.array(sites)[:,0],np.array(sites)[:,1],c=[TEAL,ORANGE],s=25)
aa[0].text(0,65,'S₁',color=TEAL);aa[0].text(800,-535,'S₂',color=ORANGE)
aa[0].set(xlim=(-100,950),ylim=(-600,450),title='(a) 两条 ±1° 测向扇区')
aa[1].set(xlim=(570,630),ylim=(150,210),title='(b) 交集与最远顶点对')
aa[1].text(571,153,f'D(P) = {dist[i,j]:.2f} m',fontsize=9)
for ax in aa:
    bounds=[(*ax.get_xlim(),),(*ax.get_ylim(),)]
    for line in ax.lines:
        xx,yy=line.get_data();p0=np.array([xx[0],yy[0]]);p1=np.array([xx[-1],yy[-1]]);d0=p1-p0;lo=0.;hi=1.
        for dim,(lower,upper) in enumerate(bounds):
            if abs(d0[dim])<1e-12:continue
            t0=(lower-p0[dim])/d0[dim];t1=(upper-p0[dim])/d0[dim];lo=max(lo,min(t0,t1));hi=min(hi,max(t0,t1))
        if lo<=hi:
            zz=np.array([p0+lo*d0,p0+hi*d0]);line.set_data(zz[:,0],zz[:,1])
        else:line.set_data([],[])

save(f,'fig16_bearing_intersection','测向误差通过取交转为可计算区域','精确几何示意','two sites (0,0),(850,-450), source(600,180), zero errors, ±1°')

# Q2 selection: same scale in three panels, actual narrow angular wedge.
f,aa=multi(3,3.25)
for ax in aa:ax.set(xlim=(-100,1650),ylim=(-1100,1100),xlabel='a (m)',aspect='equal');ax.tick_params(labelsize=8)
aa[0].set_ylabel('b (m)')
ang=np.deg2rad(1.005);w=np.array([[0,0],[1500*np.cos(ang),-1500*np.sin(ang)],[1500,0],[1500*np.cos(ang),1500*np.sin(ang)]])
aa[0].add_patch(Polygon(w,facecolor='#EBE4F1',edgecolor=PURPLE,lw=1.4));aa[0].scatter(0,0,s=22,color=TEAL)
for end,label in [((600,0),'u'),((0,600),'v')]:arrow(aa[0],(0,0),end);aa[0].text(end[0]+50,end[1]+150,label)
aa[0].text(420,-430,'5 < r ≤ 1500 m',fontsize=8);aa[0].set_title('(a) 首测候选扇区',fontsize=9)
for ax in aa[1:]:
    ax.pcolormesh(a,b,np.where(rec,1,0),cmap=ListedColormap(['white',LIGHT]),shading='auto',rasterized=True)
    ax.axhline(0,color=GRAY,lw=.6)
aa[1].plot(w[[0,1,2,3,0],0],w[[0,1,2,3,0],1],color=PURPLE,lw=1)
aa[1].text(280,540,'保证接收',fontsize=8);aa[1].text(850,-1000,'域外无保证',fontsize=8);aa[1].set_title('(b) 对全部候选均接收',fontsize=9)
aa[2].contourf(a,b,safe,levels=[.5,1.5],colors=['#F3DCA3'])
aa[2].scatter([800,800],[605,-605],c=ORANGE,s=23,zorder=5)
aa[2].text(80,1000,'Q = (800, ±605)',fontsize=8);aa[2].set_title('(c) 排除近距与退化',fontsize=9)
save(f,'fig04_q2_region','从源候选集合到接收域再到安全候选','算法三联图','analytic inequalities (7),(8); near5m exclusion in final condition')

# Distance on Pareto x-axis.
f,ax=canvas(3.5)
nd=sorted([r for r in rows if r['pareto_within_fixed_library']],key=lambda r:r['move_m'])
ax.plot([r['move_m'] for r in nd],[r['dense_sample_worst_D'] for r in nd],color=TEAL,lw=1)
for r in rows:
    xy=(r['move_m'],r['dense_sample_worst_D']);key=tuple(r['offset'])
    ax.scatter(*xy,color=ORANGE if key==(800,605) else TEAL if r['pareto_within_fixed_library'] else GRAY,s=50 if key==(800,605) else 30,zorder=3)
    ax.annotate(str(key),xy,xytext=offsets[key],textcoords='offset points',fontsize=8)
ax.set(xlim=(610,1040),ylim=(112,319),xlabel='首测点至第二检测点的移动距离 (m)',ylabel='采样最大定位直径 (m)')
save(f,'fig05_q2_tradeoff','移动更多并不总能取得更好精度','固定候选库统计','q12_verification.json: all8 offsets')

# Monotone set shrink, computed toy rather than invented quantities.
g=np.array([600.,100.]);ss=[np.array([0.,0.]),np.array([350.,-250.]),np.array([500.,100.])]
poly=np.array([[-1500.,-1500.],[1500.,-1500.],[1500.,1500.],[-1500.,1500.]])
pp=[];metrics=[]
for s in ss:
    poly=observe(poly,s,g);pp.append(poly.copy());center=(poly.min(axis=0)+poly.max(axis=0))/2
    metrics.append(dict(diameter=float(np.linalg.norm(poly[:,None]-poly[None,:],axis=2).max()),radius=float(np.linalg.norm(poly-center,axis=1).max()),center=center.tolist()))
assert metrics[-1]['radius']<20
f,aa=multi(3,3.2)
for k,ax in enumerate(aa):
    poly=pp[k];c=np.array(metrics[k]['center']);rad=metrics[k]['radius']
    ax.add_patch(Polygon(poly,facecolor='#EBE4F1',edgecolor=PURPLE,lw=1.2));ax.scatter(*g,c=RED,s=18,zorder=4)
    if k==2:ax.add_patch(Circle(c,20,fill=False,color=GREEN,lw=1.2))
    span=max(np.ptp(poly,axis=0).max()*1.18,48)
    ax.set(xlim=(c[0]-span/2,c[0]+span/2),ylim=(c[1]-span/2,c[1]+span/2),aspect='equal',xlabel='x (m)',title=f'({chr(97+k)}) 第 {k+1} 次观测',ylabel='y (m)' if k==0 else '')
    ax.tick_params(labelsize=8);ax.text(.5,1.01,f'D = {metrics[k]["diameter"]:.2f} m',transform=ax.transAxes,ha='center',fontsize=8)
    ax.set_title(f'({chr(97+k)}) 第 {k+1} 次观测',fontsize=9,pad=26)
save(f,'fig17_shrink','连续有效测向取交保留真源并收缩集合','计算示意例','zero-error toy; initial box ±1500m, source(600,100), three listed sites')
(QA/'revision_geometry.json').write_text(json.dumps({'shrink':metrics,'bearing_diameter':float(dist[i,j])},indent=2))

# Three-source teaching example, NOT actual baseline or simulator trace.
f,aa=multi(2,3.7)
sources=np.array([[700.,200.],[-600.,650.],[-400.,-800.]])
second=sources+np.array([[100,-130],[130,90],[-130,100]])
search=[seven[k] for k in [0,1,2,3,4,5,6]]
late=search+[x for pair in zip(second,sources) for x in pair]
early=[seven[0],seven[1],second[0],sources[0],seven[2],seven[3],second[1],sources[1],seven[4],seven[5],second[2],sources[2],seven[6]]
for k,(ax,route) in enumerate(zip(aa,[late,early])):
    ax.add_patch(Circle((0,0),1800,fill=False,color=DARK,lw=1))
    ax.scatter(seven[:,0],seven[:,1],color=TEAL,s=22,zorder=4)
    ax.scatter(second[:,0],second[:,1],color=ORANGE,s=22,zorder=5)
    ax.scatter(sources[:,0],sources[:,1],color=RED,marker='x',s=25,zorder=5)
    for p0,p1 in zip(route[:-1],route[1:]):
        ax.annotate('',xy=p1,xytext=p0,arrowprops=dict(arrowstyle='->',lw=.7,color=DARK,alpha=.7))
    for s in sources:
        ax.add_patch(Polygon(s+np.array([[-55,-35],[55,-35],[0,55]]),facecolor='#EBE4F1',edgecolor=PURPLE,lw=.6))
    for idx,s in enumerate(seven):
        shift=np.array([-200.,-200.]) if idx==0 else 200*s/np.linalg.norm(s)
        ax.text(*(s+shift),str(idx),fontsize=8,color=TEAL,ha='center',va='center')
    ax.set(xlim=(-2000,2000),ylim=(-2000,2000),aspect='equal',xlabel='x (m)',ylabel='y (m)' if k==0 else '',title=['(a) 搜索后集中服务','(b) 搜索与服务交错'][k],xticks=[-1500,0,1500],yticks=[-1500,0,1500])
save(f,'fig18_route_example','交错调度改变服务时机与路线结构','三源教学示意，非实测','hand-constructed route order; not the frozen comparison baseline')

# Q3 distributions with all observed runs and medians; retain worst pair explicitly.
f,aa=multi(2,3.6)
rr=[r for r in pairs if r['rounding']=='bounded']
for ax,env,label in zip(aa,['bounded','pre_round_stress'],['有界读数','舍入压力']):
    rr=[r for r in pairs if r['rounding']==env];assert len(rr)==480
    vals=[[float(r[key]) for r in rr] for key in ['baseline_s','candidate_s']]
    bp=ax.boxplot(vals,tick_labels=['冻结基线','联合方案'],patch_artist=True,widths=.45,showfliers=True,flierprops=dict(marker='.',markersize=3))
    for b0,color in zip(bp['boxes'],[GRAY,TEAL]):b0.set(facecolor=color,alpha=.6)
    ax.set(ylim=(800,5350),ylabel='总虚拟时间 (s)' if ax==aa[0] else '',title=label)
    if ax==aa[0]:
        worst=max(rr,key=lambda r:float(r['change_pct']));ys=[float(worst['baseline_s']),float(worst['candidate_s'])]
        ax.plot([1,2],ys,color=RED,marker='o',lw=1)
        ax.text(1.5,4900,'同一慢例：+93.63%',color=RED,ha='center',fontsize=8)
save(f,'fig19_q3_time_distribution','均值下降不排除单次严重退化','全部运行箱线图','q3_final_pairs.csv:480 runs per environment per arm')

# Add boxes to all six family distributions.
f,ax=canvas(3.5)
family_order=['uniform','outer','cluster','min_radius','radial','reception_edge']
values=[[r['change_pct'] for r in layout_data if r['family']==fam] for fam in family_order]
ax.boxplot(values,positions=range(6),widths=.45,showfliers=False,patch_artist=True,boxprops=dict(facecolor=LIGHT),medianprops=dict(color=DARK))
for idx,vals in enumerate(values):ax.scatter(idx+np.linspace(-.18,.18,len(vals)),vals,s=14,color=TEAL,alpha=.65,zorder=3)
ax.axhline(0,color=ORANGE,ls='--',lw=1);ax.set(xticks=range(6),xticklabels=['均匀','外缘','聚集','最小半径','窄径向','接收边缘'],ylabel='布局平均总时间变化 (%)',ylim=(-30,68),xlim=(-.5,5.5))
save(f,'fig11_q3_distribution','保留全部布局与组内四分位分布','配对箱线与散点','120 layouts,4 bounded error conditions each')

# Q4 historical distributions, keep original ablation means in text.
f,aa=multi(2,3.6)
for ax,batch,label in zip(aa,['round9_main','round9_rounding'],['有界读数：96布局','舍入压力：96布局']):
    vals=[[float(r['virtual_time_s']) for r in q4 if r['batch']==batch and r['config']==cf] for cf in ['BASE','FINAL']]
    assert all(len(v)==96 for v in vals)
    bp=ax.boxplot(vals,tick_labels=['31站初始基线','25站推荐'],patch_artist=True,widths=.45,flierprops=dict(marker='.',markersize=3))
    for patch,color in zip(bp['boxes'],[GRAY,TEAL]):patch.set(facecolor=color,alpha=.6)
    ax.set(title=label,ylim=(3000,20000),ylabel='总虚拟时间 (s)' if ax==aa[0] else '')
    ax.tick_params(axis='x',labelsize=8)
save(f,'fig14_q4_historical','25站整套方案的时间分布改善','历史验证箱线图','q4_source_data.csv:2 batches96,BASE versus FINAL')

# Improve Q4 source direction annotation and 25 station color semantics.
f,ax=canvas(3.5)
ax.add_patch(Wedge((0,0),1000,-90,90,facecolor=LIGHT,edgecolor='none'));arc=np.linspace(-np.pi,np.pi,361);ax.plot(1000*np.cos(arc),1000*np.sin(arc),color=GRAY,ls='--',lw=1);ax.plot([0,0],[-1000,1000],color=TEAL,lw=.8)
ax.scatter([0,-350,650],[0,0,250],color=[RED,TEAL,TEAL],s=30,zorder=4)
arrow(ax,(0,0),(480,0));ax.text(270,-120,'n_g',fontsize=10)
ax.text(-940,170,'背面站：无信号',fontsize=9);ax.text(100,520,'正面站',fontsize=9)
ax.text(110,-520,'发射半平面',fontsize=9);ax.text(-390,-240,'源 g',color=RED)
ax.set(xlim=(-1150,1150),ylim=(-1150,1150),aspect='equal',xlabel='relative x (m)',ylabel='relative y (m)')
save(f,'fig08_no_signal','距离近仍可能背向失联','定向反例示意','R1000m, backwardsite350m fromsource')
f,ax=canvas(4.6,bottom=.27)
for k,tt in enumerate(tri):ax.add_patch(Polygon(pts[tt],facecolor=LIGHT if k%2 else '#F6EEE4',edgecolor=GRAY,lw=.7))
ax.add_patch(Circle((0,0),1800,fill=False,color=DARK,lw=1.7))
ax.scatter(pts[1:13,0],pts[1:13,1],color=TEAL,s=24,zorder=4,label='内环 950 m')
ax.scatter(pts[13:,0],pts[13:,1],color=ORANGE,s=24,zorder=4,label='外环 1870 m')
ax.scatter(0,0,marker='*',s=95,color=DARK,zorder=5)
tt=tri[4];center=pts[tt].mean(axis=0);ax.scatter(*center,color=RED,s=20,zorder=5)
for vertex in pts[tt]:ax.annotate('',xy=vertex,xytext=center,arrowprops=dict(arrowstyle='->',lw=.9,color=PURPLE))
ax.text(-2000,2170,'36个三角形；最长边 983.60 m',fontsize=9)
ax.set(xlim=(-2150,2150),ylim=(-2200,2400),aspect='equal',xlabel='x (m)',ylabel='y (m)');ax.legend(loc='lower center',bbox_to_anchor=(.5,-.38),ncol=2,fontsize=8)
save(f,'fig09_q4_cover','任意位置由近距三角形顶点包围','连续覆盖构造','25 exactstations and36triangles')
print('Revision figures complete; shrink metrics:',metrics)
