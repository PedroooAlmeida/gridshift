import unittest
from dataclasses import replace
from decimal import Decimal

from gridshift.models import Assignment, Factory, Job, Machine
from gridshift.scenarios import demo_factory
from gridshift.scheduling import BaselineFailure, energy_cost, fcfs, validate


class SchedulingTests(unittest.TestCase):
    def tiny(self):
        return Factory(
            (Machine("m", 10),),
            (Job("j", 2, 0, 3, ("m",)),),
            tuple(map(Decimal, ["0.10", "0.30", "0.50"])),
        )

    def test_demo_is_repeatable_and_feasible(self):
        f = demo_factory()
        self.assertEqual((len(f.machines), len(f.jobs), len(f.prices_per_kwh)), (3, 15, 24))
        self.assertEqual(fcfs(f), fcfs(demo_factory()))
        self.assertEqual(validate(f, fcfs(f)), ())

    def test_cost_integrates_actual_hours(self):
        f = self.tiny()
        self.assertEqual(energy_cost(f, (Assignment("j", "m", 1, 3),)), Decimal("8.00"))
        self.assertEqual(energy_cost(f, fcfs(f)), Decimal("4.00"))

    def test_validator_catches_corrupt_schedules(self):
        f = self.tiny()
        for bad in [
            (),
            (Assignment("j", "m", -1, 1),),
            (Assignment("j", "m", 0, 1),),
            (Assignment("j", "other", 0, 2),),
            (Assignment("j", "m", 0, 2),) * 2,
            (Assignment("unknown", "m", 0, 2),),
        ]:
            with self.subTest(schedule=bad):
                self.assertTrue(validate(f, bad))
                with self.assertRaises(ValueError):
                    energy_cost(f, bad)

    def test_overlap_rejected_but_touching_allowed(self):
        f = replace(self.tiny(), jobs=(Job("a", 1, 0, 3, ("m",)), Job("b", 1, 0, 3, ("m",))))
        self.assertEqual(validate(f, (Assignment("a", "m", 0, 1), Assignment("b", "m", 1, 2))), ())
        self.assertTrue(validate(f, (Assignment("a", "m", 0, 1), Assignment("b", "m", 0, 1))))

    def test_greedy_failure_does_not_prove_infeasibility(self):
        f = replace(self.tiny(), jobs=(Job("a", 2, 0, 3, ("m",)), Job("b", 1, 0, 1, ("m",))))
        with self.assertRaises(BaselineFailure):
            fcfs(f)
        self.assertEqual(validate(f, (Assignment("b", "m", 0, 1), Assignment("a", "m", 1, 3))), ())

    def test_bad_input_and_negative_prices(self):
        with self.assertRaises(ValueError):
            replace(self.tiny(), machines=(Machine("m", -1),))
        with self.assertRaises(ValueError):
            replace(self.tiny(), prices_per_kwh=(Decimal("NaN"),))
        f = replace(self.tiny(), prices_per_kwh=(Decimal("-0.1"),) * 3)
        self.assertEqual(energy_cost(f, fcfs(f)), Decimal("-2.0"))


if __name__ == "__main__":
    unittest.main()
