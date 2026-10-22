"""Controlled ablation: hold FCFS machine assignments fixed, optimize only timing."""

from dataclasses import replace

from .optimizer import optimize
from .scheduling import energy_cost, fcfs


def savings_ablation(factory, full_result=None, time_limit=10):
    baseline = fcfs(factory)
    assignment = {a.job_id: a.machine_id for a in baseline}
    fixed = replace(
        factory, jobs=tuple(replace(j, eligible_machines=(assignment[j.id],)) for j in factory.jobs)
    )
    timing = optimize(fixed, time_limit)
    full = full_result or optimize(factory, time_limit)
    exact = timing.status == full.status == "OPTIMAL"
    base_cost = energy_cost(factory, baseline)
    return {
        "baseline_cost": base_cost,
        "fixed_machine_cost": timing.cost,
        "full_cost": full.cost,
        "timing_status": timing.status,
        "full_status": full.status,
        "exact": exact,
        "time_shift_savings": base_cost - timing.cost if exact else None,
        "additional_machine_choice_savings": timing.cost - full.cost if exact else None,
        "interpretation": "Sequential ablation: hold FCFS machines fixed, then free machine choice. "
        "Order-dependent attribution; only exact when both subproblems prove optimality.",
    }
