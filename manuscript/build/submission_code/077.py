"""Small accounting and dispatch-contract checks; no simulator is launched."""
import unittest

import numpy as np

from .service import choose


class ServiceDispatchTests(unittest.TestCase):
    def context(self, **extra):
        result = dict(first={}, cleared=set(), polys={}, bearings={},
                      channel=1, config={})
        result.update(extra)
        return result

    def test_scan_charges_unknown_channels_and_real_initial_switch(self):
        context = self.context(first={c: None for c in range(1, 16)}, channel=16)
        _, detail = choose((0, 0), [("scan", 0, (0, 0))], context)
        self.assertEqual(detail["immediate_proxy_s"], 29.0)
        self.assertEqual(detail["unknown_channel_count"], 5)

    def test_clear_preserves_channel_for_following_scan(self):
        square = np.array([[-1., -1.], [1., -1.], [1., 1.], [-1., 1.]])
        context = self.context(first={1: None}, polys={1: square}, bearings={1: 0.}, channel=2)
        selected, detail = choose((0, 0), [("localize", 1, (0, 0)),
                                          ("scan", 0, (0, 0))], context)
        self.assertEqual(selected[0], "localize")
        self.assertEqual(detail["immediate_proxy_s"], 5.0)
        self.assertEqual(detail["score_s"], 5.0 + 95.0 + 18.0)

    def test_pair_does_not_price_all_tail_stations(self):
        tasks = [("scan", j, (float(j * 10), 0.)) for j in range(4)]
        _, pair = choose((0., 0.), tasks, self.context())
        _, tour = choose((0., 0.), tasks,
                         self.context(config={"dispatch_variant": "SERVICE_TOUR"}))
        self.assertEqual(pair["horizon_tasks"], 2)
        self.assertEqual(tour["horizon_tasks"], 4)
        self.assertLess(pair["score_s"], tour["score_s"])

    def test_single_task_is_returned_unchanged(self):
        task = ("scan", 2, (100., 0.))
        selected, _ = choose((0., 0.), [task], self.context())
        self.assertIs(selected, task)


if __name__ == "__main__":
    unittest.main()
