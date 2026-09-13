"""Remove the counter constraint while preserving the complete choice set."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from question3.batch_scheduling import gate
from question3.lookahead import decide
from question3.cases import random_case,late_source_case,boundary_case
from question3.interface import Client
from question3.simulator import Simulator
from question3.strategy import run


def config():return json.loads(Path('question3/configs/round16_dev/FREE.json').read_text())


class NearestFiniteTests(unittest.TestCase):
    def test_no_filter_or_forcing_even_with_long_counter(self):
        jobs=[(1,2,(0,0),{})];remaining=[1,2]
        a,b,forced,info=gate('nearest_finite',[2],{2:None},jobs,remaining,100)
        self.assertIs(a,jobs);self.assertIs(b,remaining);self.assertFalse(forced);self.assertIsNone(info)

    def test_controller_receives_all_options_and_no_forcing(self):
        seen=[]
        def spy(current,channel,cover,remaining,jobs,first,negative,unknown,c,forced=False):
            self.assertFalse(forced);seen.append((len(remaining),len(jobs)))
            return decide(current,channel,cover,remaining,jobs,first,negative,unknown,c,forced)
        with patch('question3.strategy.decide',side_effect=spy):
            r=run(Client(Simulator(random_case(0)),'SELF'),config())
        self.assertEqual(r['status'],'complete');self.assertTrue(any(a and b for a,b in seen))

    def test_finite_distinct_tasks_and_complete_stop_including_late_channel(self):
        for case in [random_case(0),late_source_case(),boundary_case()]:
            es=[];env=Simulator(case);r=run(Client(env,'SELF'),config(),es.append)
            self.assertEqual(r['status'],'complete');self.assertFalse(env.evaluation()['remaining_channels'])
            tasks=[e for e in es if e['type']=='schedule'];scans=[e['station_id'] for e in tasks if e['task']=='scan']
            locs=[e['channel'] for e in tasks if e['task']=='localize']
            self.assertEqual(len(scans),len(set(scans)));self.assertLessEqual(len(scans),7)
            self.assertEqual(len(locs),len(set(locs)));self.assertLessEqual(len(locs),16)
            self.assertLessEqual(len(tasks),23);self.assertFalse(any(e['forced'] for e in tasks))
            if case['id']=='late_channel20_after_ten':
                self.assertIn(20,r['cleared_channels']);self.assertEqual(r['stopping_certificate']['method'],'seven_station_channel_cover')

    def test_deadline_during_extended_localization_never_completes(self):
        client=Client(Simulator(random_case(0)),'SELF');selected=[]
        def event(e):
            if e['type']=='schedule' and e['task']=='localize':
                selected.append(e)
                if len(selected)==3:client.deadline=0
        r=run(client,config(),event)
        self.assertEqual(len(selected),3);self.assertEqual(r['status'],'incomplete');self.assertFalse(r['exit_confirmed'])
