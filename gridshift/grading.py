"""Semantic extraction graders and explicit benchmark regression gates."""

import math
from decimal import Decimal

from .events import Event

SEMANTIC_FIELDS = (
    "kind",
    "start_hour",
    "end_hour",
    "reduction_kw",
    "reward_dollars",
    "penalty_dollars",
    "machine_id",
)


def grade_event(actual, expected):
    """Grade all semantic fields, including unexpected non-null values; validate first."""
    try:
        event = Event.model_validate(actual)
    except (ValueError, TypeError):
        return False
    actual = event.model_dump()
    for key in SEMANTIC_FIELDS:
        want = expected.get(key)
        got = actual.get(key)
        if key in ("reward_dollars", "penalty_dollars") and want is not None:
            want = Decimal(str(want))
        if got != want:
            return False
    return True


def regression_failures(report):
    """Each failed invariant explains why CI must fail. UNKNOWN is not a proof."""
    failures = []
    for case in report["cases"]:
        seed, result = case["seed"], case["optimized"]
        prefix = f"seed {seed}: "
        status, schedule, cost = result["status"], result["schedule"], result["cost"]
        if status not in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"):
            failures.append(prefix + "invalid solver status")
        has_solution = status in ("OPTIMAL", "FEASIBLE")
        if has_solution != (schedule is not None and cost is not None):
            failures.append(prefix + "status/solution mismatch")
        if case["validation_errors"]:
            failures.append(prefix + "invalid returned schedule")
        if (
            case.get("baseline_cost_correct") is False
            or case.get("optimized_cost_correct") is False
        ):
            failures.append(prefix + "independent accounting mismatch")
        if status == "INFEASIBLE" and (
            case["baseline_schedule"] is not None or case.get("price_aware_schedule") is not None
        ):
            failures.append(prefix + "infeasible claim contradicted by feasible baseline")
        if has_solution:
            bound = result["lower_bound_dollars"]
            if (
                bound is None
                or not math.isfinite(bound)
                or not math.isfinite(float(cost))
                or float(cost) + 1e-7 < bound
            ):
                failures.append(prefix + "invalid minimization bound")
            if status == "OPTIMAL":
                if bound is None or abs(float(cost) - bound) > 1e-7:
                    failures.append(prefix + "OPTIMAL with nonzero absolute gap")
                if case["baseline_cost"] is not None and Decimal(cost) > Decimal(
                    case["baseline_cost"]
                ):
                    failures.append(prefix + "claimed optimum worse than feasible baseline")
                if case.get("price_aware_cost") is not None and Decimal(cost) > Decimal(
                    case["price_aware_cost"]
                ):
                    failures.append(prefix + "claimed optimum worse than price-aware greedy")
    if report["event_extraction"]["passed"] != report["event_extraction"]["total"]:
        failures.append("offline event extraction regression")
    return failures
