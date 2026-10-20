"""Exhaustive enumeration is a separate oracle for tiny instances."""
import itertools
import random
import unittest
from decimal import Decimal
from gridshift.models import Assignment, Factory, Job, Machine
from gridshift.optimizer import optimize
from gridshift.scenarios import demo_factory
from gridshift.scheduling import energy_cost, fcfs, validate


def exhaustive_cost(factory):
    # Enumerate every machine/start combination, independently check occupancy
    # and compute cost without calling the optimizer's candidate builder.
    choices = [[Assignment(j.id, m, s, s + j.duration_hours)
                for m in j.eligible_machines
                for s in range(j.release_hour, j.deadline_hour - j.duration_hours + 1)]
               for j in factory.jobs]
    best = None
    powers = {m.id: m.power_kw for m in factory.machines}
    for schedule in itertools.product(*choices):
        occupied = set()
        cost = Decimal(0)
        valid = True
        for a in schedule:
            for h in range(a.start_hour, a.end_hour):
                if (a.machine_id, h) in occupied:
                    valid = False
                occupied.add((a.machine_id, h))
                cost += powers[a.machine_id] * factory.prices_per_kwh[h]
        if valid and (best is None or cost < best):
            best = cost
    return best


class OptimizerTests(unittest.TestCase):
    def test_demo_improves_baseline(self):
        f = demo_factory()
        r = optimize(f)
        self.assertEqual(r.status, "OPTIMAL")
        self.assertEqual(validate(f, r.schedule), ())
        self.assertLess(r.cost, energy_cost(f, fcfs(f)))
        self.assertAlmostEqual(r.absolute_gap_dollars, 0)

    def test_seeded_tiny_cases_against_exhaustive_oracle(self):
        for seed in range(30):
            rng = random.Random(seed)
            f = Factory((Machine("a", 10), Machine("b", 20)),
                        tuple(Job(str(i), rng.randint(1, 3), rng.randint(0, 1),
                                  rng.randint(2, 4), ("a",) if i % 2 else ("a", "b"))
                              for i in range(3)),
                        tuple(Decimal(rng.randint(-3, 8)) / 100 for _ in range(4)))
            expected = exhaustive_cost(f)
            r = optimize(f)
            with self.subTest(seed=seed):
                if expected is None:
                    self.assertEqual(r.status, "INFEASIBLE")
                    self.assertIsNone(r.schedule)
                    self.assertIsNone(r.cost)
                else:
                    self.assertEqual(r.status, "OPTIMAL")
                    self.assertEqual(r.cost, expected)
                    self.assertEqual(validate(f, r.schedule), ())
                    self.assertAlmostEqual(r.lower_bound_dollars, float(expected))

    def test_recovers_from_greedy_failure(self):
        f = Factory((Machine("m", 10),),
                    (Job("a", 2, 0, 3, ("m",)), Job("b", 1, 0, 1, ("m",))),
                    (Decimal("0.1"),) * 3)
        self.assertEqual(optimize(f).status, "OPTIMAL")

    def test_empty_job_set(self):
        f = Factory((Machine("m", 10),), (), (Decimal("0.1"),))
        r = optimize(f)
        self.assertEqual((r.status, r.schedule, r.cost), ("OPTIMAL", (), Decimal(0)))

    def test_precision_and_time_limit_guards(self):
        f = Factory((Machine("m", 10),), (), (Decimal("0.0000001"),))
        with self.assertRaises(ValueError):
            optimize(f)
        for limit in (0, -1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                optimize(demo_factory(), limit)
