"""Runtime stress with job-indexed common random numbers and paired economics.

Uncertainty is synthetic: each job independently overruns by at most one hour.
Buffered plans provide a deterministic certificate within that bounded model.
"""

import math
import random
import statistics
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING, Mapping, Optional, Sequence, Tuple, TypedDict

from .models import Assignment, Factory
from .optimizer import optimize
from .scheduling import energy_cost, hourly_load_kw, validate
from .stochastic import optimize_scenarios

if TYPE_CHECKING:
    from .agent import Decision

# Approximate simultaneous 95% intervals over at most three policy comparisons.
POLICY_INTERVAL_Z = 2.394
MAX_FAILURE_PROBABILITY = 0.05
TRAINING_SCENARIOS = 24
TRAINING_SEED_OFFSET = 100_000


class RuntimeOutcome(TypedDict):
    load_kw: dict[int, int]
    cost: Decimal
    late: bool
    cap_fail: bool
    schedule: Tuple[Assignment, ...]
    tail_price: Decimal


@dataclass(frozen=True)
class _Policy:
    name: str
    schedule: Tuple[Assignment, ...]
    bounded_runtime_certificate: bool = False


def wilson(successes: int, trials: int, z: float = 1.96) -> list[float]:
    """Binomial proportion interval at the normal quantile z."""
    p = successes / trials
    center = (p + z * z / (2 * trials)) / (1 + z * z / trials)
    radius = (
        z * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5) / (1 + z * z / trials)
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def runtime_draws(
    factory: Factory, trials: int, probability: float, seed: int
) -> list[dict[str, int]]:
    if (
        type(trials) is not int
        or trials < 1
        or not math.isfinite(probability)
        or not 0 <= probability <= 1
    ):
        raise ValueError("Trials must be a positive integer and probability finite in [0,1]")
    rng = random.Random(seed)
    # Assign the same disturbance to a job even when a policy moves it to another machine.
    ids = sorted(j.id for j in factory.jobs)
    return [{j: int(rng.random() < probability) for j in ids} for _ in range(trials)]


def realize(
    factory: Factory, schedule: Sequence[Assignment], overruns: Mapping[str, int]
) -> RuntimeOutcome:
    """Dispatch fixed machine order, postpone starts; return realized load and cost.

    Caller validates the nominal schedule once. Beyond-horizon energy is billed
    at max(0, maximum daily price), an explicit synthetic tail-price assumption.
    """
    jobs = {j.id: j for j in factory.jobs}
    load, assignments = {}, []
    late = False
    for machine in factory.machines:
        available = 0
        for a in sorted(
            (a for a in schedule if a.machine_id == machine.id), key=lambda a: a.start_hour
        ):
            start = max(a.start_hour, available)
            duration = jobs[a.job_id].duration_hours + overruns[a.job_id]
            while True:
                hit = [
                    o.end_hour
                    for o in factory.outages
                    if o.machine_id == machine.id
                    and start < o.end_hour
                    and o.start_hour < start + duration
                ]
                if not hit:
                    break
                start = max(hit)
            available = start + duration
            late |= available > jobs[a.job_id].deadline_hour
            assignments.append(Assignment(a.job_id, machine.id, start, available))
            for h in range(start, available):
                load[h] = load.get(h, 0) + machine.power_kw
    cap_fail = any(
        cap is not None and load.get(h, 0) > cap for h, cap in enumerate(factory.power_caps_kw)
    )
    tail_price = max(Decimal(0), max(factory.prices_per_kwh))
    cost = sum(
        (
            kw * (factory.prices_per_kwh[h] if h < len(factory.prices_per_kwh) else tail_price)
            for h, kw in load.items()
        ),
        Decimal(0),
    )
    return {
        "load_kw": load,
        "cost": cost,
        "late": late,
        "cap_fail": cap_fail,
        "schedule": tuple(assignments),
        "tail_price": tail_price,
    }


def simulate(
    factory: Factory, schedule: Sequence[Assignment], trials=500, overrun_probability=0.15, seed=42
):
    if validate(factory, schedule):
        raise ValueError("Stress simulation requires a validated nominal schedule")
    failures, late_trials, cap_trials = 0, 0, 0
    costs = []
    for draw in runtime_draws(factory, trials, overrun_probability, seed):
        r = realize(factory, schedule, draw)
        late_trials += r["late"]
        cap_trials += r["cap_fail"]
        failures += r["late"] or r["cap_fail"]
        costs.append(float(r["cost"]))
    return {
        "trials": trials,
        "seed": seed,
        "overrun_probability": overrun_probability,
        "failure_rate": failures / trials,
        "deadline_failure_rate": late_trials / trials,
        "cap_failure_rate": cap_trials / trials,
        "mean_realized_energy_cost": statistics.mean(costs),
        "failure_rate_95pct_interval": wilson(failures, trials),
        "assumption": "Independent one-hour job overruns; fixed machine order; synthetic stress. "
        "Beyond-horizon energy uses the nonnegative maximum daily price.",
    }


def buffered_plan(
    factory: Factory, time_limit: float = 10
) -> Tuple[Optional[Tuple[Assignment, ...]], str]:
    """Reserve d+1 hours for each job; return the nominal d-hour execution plan.

    Nonnegative machine power implies every bounded realization is a subset of
    its reservation. Thus all deadlines, outages and hourly caps remain satisfied.
    Objective minimizes energy of the reservations, not expected stochastic cost.
    """
    padded = replace(
        factory, jobs=tuple(replace(j, duration_hours=j.duration_hours + 1) for j in factory.jobs)
    )
    result = optimize(padded, time_limit)
    if result.schedule is None:
        return None, result.status
    if validate(padded, result.schedule):
        raise RuntimeError("Invalid buffered reservations")
    nominal = tuple(replace(a, end_hour=a.end_hour - 1) for a in result.schedule)
    if validate(factory, nominal):
        raise RuntimeError("Invalid nominal projection of buffered plan")
    return nominal, result.status


def _assess_policy(
    factory: Factory,
    decision: "Decision",
    policy: _Policy,
    draws: Sequence[Mapping[str, int]],
    reference: Sequence[RuntimeOutcome],
) -> dict:
    benefits, failures, delivery_failures = [], 0, 0
    event = decision.event
    for draw, base in zip(draws, reference):
        actual = realize(decision.factory, policy.schedule, draw)
        delivered = all(
            actual["load_kw"].get(hour, 0) <= decision.factory.power_caps_kw[hour]
            for hour in range(event.start_hour, event.end_hour)
        )
        cashflow = event.reward_dollars if delivered else -event.penalty_dollars
        benefits.append(float(cashflow - (actual["cost"] - base["cost"])))
        delivery_failures += not delivered
        failures += actual["late"] or actual["cap_fail"]

    trials = len(draws)
    mean_profit = statistics.mean(benefits)
    half_width = (
        POLICY_INTERVAL_Z * statistics.stdev(benefits) / math.sqrt(trials)
        if trials > 1
        else float("inf")
    )
    profit_interval = [mean_profit - half_width, mean_profit + half_width]
    risk_interval = wilson(failures, trials, z=POLICY_INTERVAL_Z)
    passes_risk = policy.bounded_runtime_certificate or risk_interval[1] <= MAX_FAILURE_PROBABILITY
    return {
        "policy": policy.name,
        "schedule": policy.schedule,
        "nominal_cost": energy_cost(factory, policy.schedule),
        "bounded_runtime_certificate": policy.bounded_runtime_certificate,
        "failure_rate": failures / trials,
        "failure_rate_95pct_interval": risk_interval,
        "delivery_failure_rate": delivery_failures / trials,
        "mean_incremental_profit": mean_profit,
        "profit_mean_95pct_interval": profit_interval,
        "qualifies": passes_risk and profit_interval[0] > 0,
    }


def assess_offer(
    factory: Factory,
    decision: "Decision",
    trials: int = 500,
    probability: float = 0.15,
    seed: int = 42,
    time_limit: float = 10,
) -> dict:
    """Compare nominal, buffered and SAA plans under paired execution disturbances.

    Require a positive lower profit bound and either a bounded-runtime certificate
    or an upper failure bound of at most 5%. Intervals account for three comparisons.
    """
    if (
        decision.reference is None
        or decision.reference.schedule is None
        or decision.candidate is None
        or decision.candidate.schedule is None
    ):
        raise ValueError("Reference and candidate schedules are required")

    draws = runtime_draws(factory, trials, probability, seed)
    reference = [realize(factory, decision.reference.schedule, draw) for draw in draws]
    candidates = [_Policy("nominal", decision.candidate.schedule)]
    buffered, buffered_status = buffered_plan(decision.factory, time_limit)
    if buffered is not None:
        candidates.append(_Policy("buffered", buffered, bounded_runtime_certificate=True))

    # Keep training draws separate from the paired policy-evaluation draws.
    training_draws = runtime_draws(
        factory, TRAINING_SCENARIOS, probability, seed + TRAINING_SEED_OFFSET
    )
    stochastic = optimize_scenarios(
        factory,
        decision.event,
        hourly_load_kw(factory, decision.reference.schedule),
        training_draws,
        time_limit,
    )
    if stochastic.schedule is not None:
        candidates.append(_Policy("stochastic", stochastic.schedule))

    policies = [
        _assess_policy(factory, decision, policy, draws, reference) for policy in candidates
    ]
    eligible = [policy for policy in policies if policy["qualifies"]]
    selected = max(eligible, key=lambda policy: policy["mean_incremental_profit"], default=None)
    return {
        "trials": trials,
        "seed": seed,
        "overrun_probability": probability,
        "policies": policies,
        "buffered_solver_status": buffered_status,
        "stochastic_solver_status": stochastic.status,
        "stochastic_training_objective": stochastic.expected_net_cost,
        "stochastic_training_bound": stochastic.lower_bound,
        "selected_policy": selected["policy"] if selected else None,
        "recommendation": "RECOMMEND" if selected else "REVIEW",
        "assumptions": "Synthetic independent overruns of at most one hour; common random numbers by job. "
        "Reward forfeited and penalty paid on delivery failure. Realized energy included; "
        "deadline violations are gated, never monetized. Mean intervals are approximate, "
        "Bonferroni-adjusted for three policy comparisons, not model-calibration guarantees. "
        f"The SAA plan uses {TRAINING_SCENARIOS} separate training scenarios.",
    }
