"""Small checks for the new ordering heuristic, without any simulator truth."""
import copy
import unittest

import numpy as np

from .discovery import choose
from question3.innovation.routing import choose as choose_tour


class DiscoveryTests(unittest.TestCase):
    def context(self):
        return dict(polys={}, bearings={}, first={}, cleared=set(),
                    stations=[(0., 0.), (1125., 0.), (0., 0.)], visited={0},
                    negative={c: {0} for c in range(1, 21)},
                    config={'dispatch_variant': 'coverage_order'})

    def test_negative_record_changes_search_order_without_mutation(self):
        context = self.context()
        before = copy.deepcopy(context)
        tasks = [('scan', 2, (0., 0.)), ('scan', 1, (1125., 0.))]
        self.assertEqual(choose_tour((0., 0.), tasks, True)[0][1], 2)
        selected, details = choose((0., 0.), tasks, context)
        self.assertEqual(selected[1], 1)
        scores = {row['target']: row for row in details['scores']}
        self.assertEqual(scores[2]['value'], 0.)
        self.assertGreater(scores[1]['value'], 0.)
        self.assertEqual(context, before)

    def test_order_variant_preserves_selected_service(self):
        context = self.context()
        context['first'][1] = ((0., 0.), 0.)
        context['polys'][1] = np.array([[0., 0.], [1., 0.], [0., 1.]])
        context['bearings'][1] = 0.
        tasks = [('localize', 1, (0., 0.)), ('scan', 1, (1125., 0.))]
        self.assertEqual(choose((0., 0.), tasks, context)[0][0], 'localize')

    def test_count_upper_limit_gives_no_fabricated_discovery_reward(self):
        context = self.context()
        context['first'] = {c: ((0., 0.), 0.) for c in range(1, 17)}
        tasks = [('scan', 2, (0., 0.)), ('scan', 1, (1125., 0.))]
        selected, details = choose((0., 0.), tasks, context)
        self.assertEqual(selected, choose_tour((0., 0.), tasks, True)[0])
        self.assertTrue(all(row['value'] == 0 for row in details['scores']))


if __name__ == '__main__':
    unittest.main()
