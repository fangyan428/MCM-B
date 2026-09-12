"""Dispatcher exposing only public actions to every compared policy."""
from .frozen.question4.strategy import run as frozen_run
from question4.innovation.strategy import run as historical_run, BASELINE_CONFIG


def run(client,config=None,log=lambda row:None):
    config=dict(config or {})
    family=config.pop('family')
    if family=='baseline':
        if config:raise ValueError('Frozen baseline has no experimental parameters')
        return frozen_run(client,BASELINE_CONFIG,log)
    if family=='historical':
        if config:raise ValueError('Historical reference configuration is fixed')
        return historical_run(client,dict(mechanism='parallax',sharing='gated'),log)
    if family=='scheduling':
        from .scheduling import run as method
    elif family=='coverage':
        from .coverage import run as method
    elif family=='local':
        from .local_mechanisms import run as method
    else:raise ValueError('Unknown mechanism family')
    return method(client,config,log)
