"""Contract delivery must be correct even without objective minimization."""

import unittest

from ortools.sat.python import cp_model

from gridshift.stochastic import _delivery_indicator


class SettlementTests(unittest.TestCase):
    def test_delivery_cannot_disagree_with_hourly_load(self):
        for loads, expected in [([0, 10], 1), ([1, 10], 0), ([0, 11], 0)]:
            with self.subTest(loads=loads):
                model = cp_model.CpModel()
                delivered = _delivery_indicator(model, loads, [0, 10], "delivery")
                model.add(delivered == 1 - expected)
                self.assertEqual(cp_model.CpSolver().solve(model), cp_model.INFEASIBLE)
