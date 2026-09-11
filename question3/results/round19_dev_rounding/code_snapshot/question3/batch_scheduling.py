"""Batch boundary changes only scheduling, not evidence or stopping state."""


def gate(mode,pending,cached,jobs,remaining,consecutive):
    if mode=='nearest_finite':return jobs,remaining,False,None
    if mode=='known_batch' and pending:
        return jobs,[],False,dict(mode=mode,batch_channels=sorted(pending),deferred_stations=list(remaining))
    if mode=='cached_batch' and cached:
        eligible=[j for j in jobs if j[1] in cached]
        if not eligible:raise RuntimeError('Cached batch has no eligible task')
        return eligible,[],False,dict(mode=mode,batch_channels=sorted(cached),deferred_stations=list(remaining))
    return jobs,remaining,bool(remaining and consecutive>=2),None
