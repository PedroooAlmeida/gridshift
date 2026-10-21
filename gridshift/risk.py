"""Runtime stress with job-indexed common random numbers and paired economics.

Uncertainty is synthetic: each job independently overruns by at most one hour.
Buffered plans provide a deterministic certificate within that bounded model.
"""
from dataclasses import replace
from decimal import Decimal
import math
import random
import statistics
from typing import Sequence
from .models import Assignment, Factory
from .scheduling import validate, energy_cost
from .optimizer import optimize


def wilson(successes, trials, z=1.96):
    p = successes / trials
    center = (p + z*z/(2*trials))/(1+z*z/trials)
    radius = z*((p*(1-p)/trials+z*z/(4*trials*trials))**0.5)/(1+z*z/trials)
    return [max(0.0, center-radius), min(1.0, center+radius)]


def runtime_draws(factory, trials, probability, seed):
    if type(trials) is not int or trials < 1 or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Trials must be a positive integer and probability finite in [0,1]")
    rng = random.Random(seed)
    # Assign the same disturbance to a job even when a policy moves it to another machine.
    ids = sorted(j.id for j in factory.jobs)
    return [{j: int(rng.random() < probability) for j in ids} for _ in range(trials)]


def realize(factory, schedule, overruns):
    """Dispatch fixed machine order, postpone starts; return realized load and cost.

    Caller validates the nominal schedule once. Beyond-horizon energy is billed
    at max(0, maximum daily price), an explicit synthetic tail-price assumption.
    """
    jobs = {j.id: j for j in factory.jobs}
    load, assignments = {}, []
    late = False
    for machine in factory.machines:
        available = 0
        for a in sorted((a for a in schedule if a.machine_id == machine.id), key=lambda a: a.start_hour):
            start = max(a.start_hour, available)
            duration = jobs[a.job_id].duration_hours + overruns[a.job_id]
            while True:
                hit = [o.end_hour for o in factory.outages if o.machine_id == machine.id
                       and start < o.end_hour and o.start_hour < start + duration]
                if not hit:
                    break
                start = max(hit)
            available = start + duration
            late |= available > jobs[a.job_id].deadline_hour
            assignments.append(Assignment(a.job_id, machine.id, start, available))
            for h in range(start, available):
                load[h] = load.get(h, 0) + machine.power_kw
    cap_fail = any(cap is not None and load.get(h, 0) > cap
                   for h, cap in enumerate(factory.power_caps_kw))
    tail_price = max(Decimal(0), max(factory.prices_per_kwh))
    cost = sum((kw * (factory.prices_per_kwh[h] if h < len(factory.prices_per_kwh) else tail_price)
                for h, kw in load.items()), Decimal(0))
    return {"load_kw": load, "cost": cost, "late": late, "cap_fail": cap_fail,
            "schedule": tuple(assignments), "tail_price": tail_price}


def simulate(factory: Factory, schedule: Sequence[Assignment], trials=500,
             overrun_probability=0.15, seed=42):
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
    return {"trials": trials, "seed": seed, "overrun_probability": overrun_probability,
            "failure_rate": failures/trials, "deadline_failure_rate": late_trials/trials,
            "cap_failure_rate": cap_trials/trials, "mean_realized_energy_cost": statistics.mean(costs),
            "failure_rate_95pct_interval": wilson(failures, trials),
            "assumption": "Independent one-hour job overruns; fixed machine order; synthetic stress. "
                          "Beyond-horizon energy uses the nonnegative maximum daily price."}


def buffered_plan(factory, time_limit=10):
    """Reserve d+1 hours for each job; return the nominal d-hour execution plan.

    Nonnegative machine power implies every bounded realization is a subset of
    its reservation. Thus all deadlines, outages and hourly caps remain satisfied.
    Objective minimizes energy of the reservations, not expected stochastic cost.
    """
    padded = replace(factory, jobs=tuple(replace(j, duration_hours=j.duration_hours+1) for j in factory.jobs))
    result = optimize(padded, time_limit)
    if result.schedule is None:
        return None, result.status
    if validate(padded, result.schedule):
        raise RuntimeError("Invalid buffered reservations")
    nominal = tuple(replace(a, end_hour=a.end_hour-1) for a in result.schedule)
    if validate(factory, nominal):
        raise RuntimeError("Invalid nominal projection of buffered plan")
    return nominal, result.status


def assess_offer(factory, decision, trials=500, probability=0.15, seed=42, time_limit=10):
    """Compare three candidates under paired disturbances, then apply a risk gate.

    Positive economics require a positive lower end of an approximate paired-mean
    95% interval; feasibility requires a <=5% Wilson upper bound OR a certificate.
    This evaluates a finite policy set; it is not globally stochastic-optimal.
    """
    if decision.reference is None or decision.reference.schedule is None or decision.candidate is None or decision.candidate.schedule is None:
        raise ValueError("Reference and candidate schedules are required")
    event = decision.event
    draws = runtime_draws(factory, trials, probability, seed)
    reference = [realize(factory, decision.reference.schedule, d) for d in draws]
    buffered, buffered_status = buffered_plan(decision.factory, time_limit)
    candidates = [("nominal", decision.candidate.schedule, False)]
    if buffered is not None:
        candidates.append(("buffered", buffered, True))
    from .stochastic import optimize_scenarios
    from .scheduling import hourly_load_kw
    # Training scenarios are disjoint from the evaluation disturbances above.
    saa = optimize_scenarios(factory, event, hourly_load_kw(factory, decision.reference.schedule),
                             runtime_draws(factory, 24, probability, seed+100000), time_limit)
    if saa.schedule is not None:
        candidates.append(("stochastic", saa.schedule, False))
    policies = []
    for name, schedule, certificate in candidates:
        benefits, fails, delivery_fails = [], 0, 0
        for draw, base in zip(draws, reference):
            actual = realize(decision.factory, schedule, draw)
            delivered = all(actual["load_kw"].get(h, 0) <= decision.factory.power_caps_kw[h]
                            for h in range(event.start_hour, event.end_hour))
            cashflow = event.reward_dollars if delivered else -event.penalty_dollars
            benefits.append(float(cashflow - (actual["cost"] - base["cost"])))
            delivery_fails += not delivered
            fails += actual["late"] or actual["cap_fail"]
        mean = statistics.mean(benefits)
        half_width = 2.394 * statistics.stdev(benefits) / math.sqrt(trials) if trials > 1 else float("inf")
        interval = [mean-half_width, mean+half_width]
        risk_interval = wilson(fails, trials, z=2.394)
        feasible = certificate or risk_interval[1] <= 0.05
        policies.append({"policy": name, "schedule": schedule, "nominal_cost": energy_cost(factory, schedule),
                         "bounded_runtime_certificate": certificate, "failure_rate": fails/trials,
                         "failure_rate_95pct_interval": risk_interval,
                         "delivery_failure_rate": delivery_fails/trials,
                         "mean_incremental_profit": mean, "profit_mean_95pct_interval": interval,
                         "qualifies": feasible and interval[0] > 0})
    eligible = [p for p in policies if p["qualifies"]]
    selected = max(eligible, key=lambda p: p["mean_incremental_profit"]) if eligible else None
    return {"trials": trials, "seed": seed, "overrun_probability": probability, "policies": policies,
            "buffered_solver_status": buffered_status, "stochastic_solver_status": saa.status,
            "stochastic_training_objective": saa.expected_net_cost, "stochastic_training_bound": saa.lower_bound, "selected_policy": selected["policy"] if selected else None,
            "recommendation": "RECOMMEND" if selected else "REVIEW",
            "assumptions": "Synthetic independent overruns of at most one hour; common random numbers by job. "
                           "Reward forfeited and penalty paid on delivery failure. Realized energy included; "
                           "deadline violations are gated, never monetized. Mean intervals are approximate, "
                           "Bonferroni-adjusted for three policy comparisons, not model-calibration guarantees. "
                           "The SAA plan is optimized on 24 disjoint training scenarios, then evaluated out of sample."}
