"""Baseline strategy only. Observation API: enter/measure/clear/exit.
No imports of case generation or simulator; no access to hidden count/locations/R.
"""
from .geometry import stations, station_cover_bound, second_point, optical_plan

class Incomplete(RuntimeError):pass


def run(client, config, event=lambda data:None):
    cover=stations()
    if station_cover_bound()>=1000:raise ValueError('Invalid search coverage')
    negative={c:set() for c in range(1,21)}
    first={};cleared=set();regions=[];exit_confirmed=False
    client.enter()
    failure=None
    try:
        # Search first, then localize in channel order. Intentionally simple baseline.
        for station_id,s in enumerate(cover):
            for channel in range(1,21):
                if channel in first or channel in cleared:continue
                response=client.measure(s,channel,phase='search')
                kind=response['measure_result']
                if kind=='no_signal':negative[channel].add(station_id)
                elif kind=='near':
                    if client.clear(s,channel,phase='near')['clear_result']!='success':
                        raise Incomplete('near followed by failed clear')
                    cleared.add(channel)
                elif kind=='direction':first[channel]=(s,response['svd_deg'])
                else:raise Incomplete('Unknown measure result')
        event(dict(type='coverage_complete',detected=sorted(first),cleared=sorted(cleared),
                   absent=[c for c in negative if len(negative[c])==len(cover)]))
        for channel in sorted(first):
            s,theta=first[channel]
            q=second_point(s,theta,config['second_offset'],config['error_deg'],config['min_angle_deg'])
            r=client.measure(q,channel,phase='localization')
            if r['measure_result']=='near':
                points=[q];certificate=dict(planned_clear_calls=1,covering_radius=5)
            elif r['measure_result']=='direction':
                points,certificate=optical_plan(s,theta,q,r['svd_deg'],config['error_deg'],
                                                config['optical_cell_m'],config['max_optical_points'])
            else:raise Incomplete('Guaranteed-reception second point returned no_signal')
            certificate.update(channel=channel,first_position=s,second_position=q)
            regions.append(certificate);event(dict(type='localization',**certificate))
            for p in points:
                if client.clear(p,channel,phase='optical')['clear_result']=='success':
                    cleared.add(channel);break
            else:raise Incomplete('All optical covering points failed: model/protocol inconsistency')
        # A cleared channel or seven accepted negative station observations per channel.
        complete=all(c in cleared or len(negative[c])==len(cover) for c in range(1,21))
        if not complete:raise Incomplete('Stopping certificate is incomplete')
        # Count bounds only catch inconsistent environments; never trigger early success.
        if not 10<=len(cleared)<=16:raise Incomplete('Cleared count contradicts Q3 count bounds')
        exit_confirmed=client.exit()['exit_reason']=='user_exit'
    except (RuntimeError, ValueError, KeyError) as exc:
        failure=f'{type(exc).__name__}: {exc}'
        # No blind exit after an uncertain transport action or a closed/time-expired API.
        # The operator sees incomplete; a timeout is never relabelled success.
    result=dict(status='complete' if failure is None and exit_confirmed else 'incomplete',
                failure=failure,exit_confirmed=exit_confirmed,cleared_channels=sorted(cleared),
                absent_channels=[c for c in negative if len(negative[c])==len(cover)],
                negative_station_ids={str(c):sorted(v) for c,v in negative.items()},
                station_positions=cover,regions=regions,metrics=client.metrics())
    event(dict(type='strategy_result',**result))
    return result
