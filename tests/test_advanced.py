"""Independent stochastic oracles, policy safety, and evaluation-boundary tests."""

import itertools
import random
import unittest
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gridshift.agent import execute, parse_anthropic, run
from gridshift.calibration import fit_overrun_probability
from gridshift.evaluate import evaluate
from gridshift.events import Event
from gridshift.grading import grade_event, regression_failures
from gridshift.models import Assignment, Factory, Job, Machine, Outage
from gridshift.risk import assess_offer, buffered_plan, realize, runtime_draws
from gridshift.scheduling import validate
from gridshift.stochastic import optimize_scenarios


class AdvancedTests(unittest.TestCase):
    def test_stochastic_optimum_against_independent_enumeration(self):
        for seed in range(12):
            rng = random.Random(seed)
            f = Factory(
                (Machine("a", 10), Machine("b", 20)),
                (Job("j", 1, 0, 4, ("a", "b")), Job("k", 1, 0, 4, ("a", "b"))),
                tuple(Decimal(rng.randint(-2, 8)) / 10 for _ in range(4)),
                outages=(Outage("a", 1, 2),) if seed % 2 else (),
                power_caps_kw=(20, 20, 30, 30),
            )
            event = Event(
                kind="demand_response",
                start_hour=2,
                end_hour=3,
                reduction_kw=10,
                reward_dollars=Decimal(3),
                penalty_dollars=Decimal(7),
            )
            draws = [{"j": 0, "k": 0}, {"j": 1, "k": 0}, {"j": 0, "k": 1}]
            reference = [20] * 4
            best = None
            for placements in itertools.product(
                list(itertools.product(("a", "b"), range(4))), repeat=2
            ):
                total, valid = Decimal(0), True
                for draw in draws:
                    occupied, load = set(), [0] * 4
                    for job, (machine, start) in zip(f.jobs, placements):
                        end = start + 1 + draw[job.id]
                        if end > 4:
                            valid = False
                            break
                        for h in range(start, end):
                            if (machine, h) in occupied or any(
                                o.machine_id == machine and o.start_hour <= h < o.end_hour
                                for o in f.outages
                            ):
                                valid = False
                            occupied.add((machine, h))
                            load[h] += 10 if machine == "a" else 20
                    if any(kw > cap for kw, cap in zip(load, f.power_caps_kw)):
                        valid = False
                    total += sum((kw * p for kw, p in zip(load, f.prices_per_kwh)), Decimal(0))
                    total += -event.reward_dollars if load[2] <= 10 else event.penalty_dollars
                if valid and (best is None or total / len(draws) < best):
                    best = total / len(draws)
            result = optimize_scenarios(f, event, reference, draws)
            with self.subTest(seed=seed):
                self.assertEqual(result.status, "OPTIMAL")
                self.assertEqual(result.expected_net_cost, best)
                self.assertAlmostEqual(result.lower_bound, float(best))

    def test_buffered_certificate_exhaustive_bounded_runtimes(self):
        f = Factory(
            (Machine("m", 10),),
            tuple(Job(str(i), 1, 0, 7, ("m",)) for i in range(3)),
            (Decimal(".1"),) * 7,
            outages=(Outage("m", 2, 3),),
            power_caps_kw=(10,) * 7,
        )
        schedule, status = buffered_plan(f)
        self.assertEqual(status, "OPTIMAL")
        for bits in itertools.product((0, 1), repeat=3):
            draw = dict(zip((j.id for j in f.jobs), bits))
            actual = realize(f, schedule, draw)
            changed = replace(
                f,
                jobs=tuple(
                    replace(j, duration_hours=j.duration_hours + draw[j.id]) for j in f.jobs
                ),
            )
            self.assertEqual(validate(changed, actual["schedule"]), ())
            self.assertFalse(actual["late"] or actual["cap_fail"])

    def test_random_draws_are_associated_with_jobs(self):
        f = Factory(
            (Machine("m", 10),),
            (Job("z", 1, 0, 3, ("m",)), Job("a", 1, 0, 3, ("m",))),
            (Decimal(".1"),) * 3,
        )
        self.assertEqual(
            runtime_draws(f, 50, 0.2, 7),
            runtime_draws(replace(f, jobs=tuple(reversed(f.jobs))), 50, 0.2, 7),
        )
        for p in (-1, float("nan"), 1.1):
            with self.assertRaises(ValueError):
                runtime_draws(f, 10, p, 0)

    def test_actual_energy_tail_price_and_failures(self):
        f = Factory(
            (Machine("m", 10),),
            (Job("j", 1, 0, 2, ("m",)),),
            (Decimal(".1"), Decimal(".5")),
            power_caps_kw=(10, 0),
        )
        actual = realize(f, (Assignment("j", "m", 1, 2),), {"j": 1})
        self.assertEqual(actual["cost"], Decimal(10))
        self.assertTrue(actual["late"] and actual["cap_fail"])

    def test_anthropic_adapter_rejects_incomplete_or_multiple_tools(self):
        event = {"kind": "outage", "machine_id": "m", "start_hour": 0, "end_hour": 1}
        block = SimpleNamespace(type="tool_use", name="submit_event", input=event)
        client = Mock()
        client.messages.create.return_value = SimpleNamespace(
            stop_reason="tool_use", content=[block]
        )
        self.assertEqual(parse_anthropic("text", client).kind, "outage")
        for stop, blocks in [
            ("end_turn", []),
            ("max_tokens", [block]),
            ("tool_use", [block, block]),
        ]:
            client.messages.create.return_value = SimpleNamespace(stop_reason=stop, content=blocks)
            with self.assertRaises(ValueError):
                parse_anthropic("text", client)
        block.input = {"kind": "demand_response"}
        client.messages.create.return_value = SimpleNamespace(
            stop_reason="tool_use", content=[block]
        )
        with self.assertRaises(ValueError):
            parse_anthropic("text", client)

    def test_offline_workflow_does_not_use_provider(self):
        f = Factory((Machine("m", 10),), (Job("j", 1, 0, 2, ("m",)),), (Decimal(".1"),) * 2)
        with (
            patch("gridshift.agent.parse_anthropic", side_effect=AssertionError("No API")),
            patch("gridshift.agent.parse_llm", side_effect=AssertionError("No API")),
        ):
            self.assertEqual(run(f, "Machine m unavailable between 0 and 1").action, "REPLAN")

    def test_semantic_grader_decimal_equality_and_extra_fields(self):
        expected = dict(
            kind="demand_response",
            start_hour=0,
            end_hour=1,
            reduction_kw=10,
            reward_dollars="10",
            penalty_dollars="0",
        )
        self.assertTrue(grade_event(dict(expected, reward_dollars="10.00"), expected))
        self.assertFalse(grade_event(dict(expected, machine_id="m"), expected))
        self.assertFalse(grade_event({"kind": "clarify"}, {"kind": "clarify"}))

    def test_regression_gates_detect_accounting_bounds_and_dominance(self):
        report = evaluate(count=3, start_seed=1)
        self.assertEqual(regression_failures(report), [])
        case = next(c for c in report["cases"] if c["optimized"]["cost"] is not None)
        for mutation in ("bound", "accounting", "dominance", "infeasible"):
            changed = deepcopy(report)
            target = next(c for c in changed["cases"] if c["seed"] == case["seed"])
            if mutation == "bound":
                target["optimized"]["lower_bound_dollars"] = float("nan")
            if mutation == "accounting":
                target["optimized_cost_correct"] = False
            if mutation == "dominance":
                target["baseline_cost"] = "-99999"
            if mutation == "infeasible":
                target["optimized"].update(status="INFEASIBLE", schedule=None, cost=None)
                target["baseline_schedule"] = []
            self.assertTrue(regression_failures(changed), mutation)

    def test_risk_gate_rejects_fragile_nominal_and_settles_actual_profit(self):
        f = Factory(
            (Machine("m", 10),),
            (Job("j", 1, 0, 3, ("m",)),),
            (Decimal(".1"), Decimal(".5"), Decimal(".2")),
        )
        event = Event(
            kind="demand_response",
            start_hour=0,
            end_hour=1,
            reduction_kw=10,
            reward_dollars=Decimal(10),
            penalty_dollars=Decimal(20),
        )
        decision = execute(f, event)
        report = assess_offer(f, decision, trials=100, probability=1)
        nominal = next(p for p in report["policies"] if p["policy"] == "nominal")
        buffered = next(p for p in report["policies"] if p["policy"] == "buffered")
        self.assertEqual(nominal["failure_rate"], 1)
        self.assertFalse(nominal["qualifies"])
        self.assertEqual(buffered["failure_rate"], 0)
        self.assertEqual(buffered["mean_incremental_profit"], 9)
        self.assertTrue(buffered["qualifies"])
        self.assertNotEqual(report["selected_policy"], "nominal")

    def test_runtime_fit_uses_observations_and_validates_labels(self):
        self.assertEqual(fit_overrun_probability([0, 1] * 50)["probability"], 0.5)
        self.assertLess(fit_overrun_probability([0] * 100)["probability"], 0.01)
        for values in ([], [2], [True]):
            with self.assertRaises(ValueError):
                fit_overrun_probability(values)
