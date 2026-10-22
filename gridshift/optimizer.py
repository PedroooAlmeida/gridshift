"""Time-indexed CP-SAT: one binary decision per legal job/machine/start."""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from ortools.sat.python import cp_model

from .models import Assignment, Factory
from .scheduling import energy_cost, validate


@dataclass(frozen=True)
class OptimizationResult:
    status: str
    schedule: Optional[Tuple[Assignment, ...]]
    cost: Optional[Decimal]
    lower_bound_dollars: Optional[float]
    wall_time_seconds: float

    @property
    def absolute_gap_dollars(self) -> Optional[float]:
        if self.cost is None or self.lower_bound_dollars is None:
            return None
        return max(0.0, float(self.cost) - self.lower_bound_dollars)


def optimize(factory: Factory, time_limit_seconds: float = 10.0) -> OptimizationResult:
    if not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("Time limit must be finite and positive")
    # CP-SAT requires integer coefficients. Preserve up to six decimal places;
    # reject more precise prices rather than silently change the economics.
    places = max(0, max(-p.as_tuple().exponent for p in factory.prices_per_kwh))
    if places > 6:
        raise ValueError("Optimizer supports prices with at most six decimal places")
    scale = 10**places
    prices = [int(p * scale) for p in factory.prices_per_kwh]
    power = {m.id: m.power_kw for m in factory.machines}
    model = cp_model.CpModel()
    occupancy = {(m.id, h): [] for m in factory.machines for h in range(len(prices))}
    candidates = []
    objective = []
    coefficient_budget = 0
    for job in factory.jobs:
        choices = []
        for machine in sorted(set(job.eligible_machines)):
            for start in range(job.release_hour, job.deadline_hour - job.duration_hours + 1):
                end = start + job.duration_hours
                if any(
                    o.machine_id == machine and start < o.end_hour and o.start_hour < end
                    for o in factory.outages
                ):
                    continue
                x = model.new_bool_var(f"{job.id}_{machine}_{start}")
                assignment = Assignment(job.id, machine, start, end)
                cost = power[machine] * sum(prices[start:end])
                coefficient_budget += abs(cost)
                candidates.append((x, assignment))
                choices.append(x)
                objective.append(cost * x)
                for hour in range(start, end):
                    occupancy[machine, hour].append(x)
        # Empty choices means this mandatory job cannot fit its window.
        model.add(sum(choices) == 1)
    for choices in occupancy.values():
        model.add(sum(choices) <= 1)
    if factory.power_caps_kw:
        for h, cap in enumerate(factory.power_caps_kw):
            if cap is not None:
                model.add(
                    sum(
                        power[a.machine_id] * x
                        for x, a in candidates
                        if a.start_hour <= h < a.end_hour
                    )
                    <= cap
                )
    # Conservative limit also keeps reported floating-point bounds well-scaled.
    if coefficient_budget >= 2**50:
        raise ValueError("Objective coefficients exceed supported numeric range")
    model.minimize(sum(objective))
    issue = model.validate()
    if issue:
        raise ValueError("Invalid optimization model: " + issue)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    label = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return OptimizationResult(label, None, None, None, solver.wall_time)
    schedule = tuple(a for x, a in candidates if solver.value(x))
    errors = validate(factory, schedule)
    if errors:
        raise RuntimeError("Solver output failed independent validation: " + "; ".join(errors))
    cost = energy_cost(factory, schedule)
    chosen_cost = sum(
        power[a.machine_id] * sum(prices[a.start_hour : a.end_hour]) for a in schedule
    )
    if abs(solver.objective_value - chosen_cost) > 0.25:
        raise RuntimeError("Returned schedule does not match the solver objective")
    if solver.best_objective_bound > chosen_cost + 0.25:
        raise RuntimeError("Minimization bound exceeds incumbent cost")
    if cost != Decimal(chosen_cost) / scale:
        raise RuntimeError("Independent accounting disagrees with solver coefficients")
    return OptimizationResult(
        label, schedule, cost, solver.best_objective_bound / scale, solver.wall_time
    )
