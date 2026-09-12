"""Receding open tour through public feasible-set centres and required scans."""
import math

def choose(current,jobs,global_tour=True):
    # job = (kind,id,point). Unknown true endpoints are never used.
    if not global_tour:
        return min(jobs,key=lambda j:(math.dist(current,j[2]),j[0],j[1])),None
    n=len(jobs)
    distance=[[math.dist(a[2],b[2]) for b in jobs] for a in jobs]
    entry=[math.dist(current,j[2]) for j in jobs]
    def length(route):
        return entry[route[0]]+sum(distance[a][b] for a,b in zip(route,route[1:]))
    candidates=[]
    for start in range(n):
        route=[start];left=set(range(n))-{start}
        while left:
            nxt=min(left,key=lambda k:(distance[route[-1]][k],k))
            route.append(nxt);left.remove(nxt)
        # Strict improvement, finite permutations; iteration is not a tuning budget.
        while True:
            cost=length(route);improvement=None
            for i in range(n-1):
                for j in range(i+1,n):
                    alt=route[:i]+list(reversed(route[i:j+1]))+route[j+1:]
                    value=length(alt)
                    if value<cost-1e-7 and (improvement is None or (value,alt)<improvement):
                        improvement=(value,alt)
            if improvement is None:break
            route=improvement[1]
        candidates.append((length(route),route))
    cost,route=min(candidates)
    return jobs[route[0]],dict(length_m=cost,tour=[dict(task=jobs[k][0],target=jobs[k][1],point=list(jobs[k][2])) for k in route])
