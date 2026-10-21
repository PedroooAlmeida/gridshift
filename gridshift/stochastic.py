"""Static sample-average approximation (SAA) with nonanticipative placements.

Machine and planned start are shared across all training scenarios. Deadlines,
resource limits and outages are hard in every sampled scenario. Demand-response
success can vary by scenario and determines reward/penalty in the objective.
Out-of-sample dispatch and grading are separate from this optimization model.
"""
from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Optional, Tuple
from ortools.sat.python import cp_model
from .models import Assignment
from .scheduling import validate


@dataclass(frozen=True)
class StochasticResult:
    status: str
    schedule: Optional[Tuple[Assignment, ...]]
    expected_net_cost: Optional[Decimal]
    lower_bound: Optional[float]
    scenario_count: int
    wall_seconds: float


def optimize_scenarios(factory, event, reference_load, scenarios, time_limit=10):
    if not scenarios or len(scenarios) > 256:
        raise ValueError("Use 1–256 training scenarios")
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("Invalid time limit")
    ids = {j.id for j in factory.jobs}
    if event.kind != "demand_response" or event.end_hour > len(factory.prices_per_kwh):
        raise ValueError("A complete in-horizon offer is required")
    if len(reference_load) != len(factory.prices_per_kwh):
        raise ValueError("Reference load must cover the horizon")
    if any(set(d) != ids or any(type(v) is not int or v not in (0, 1) for v in d.values()) for d in scenarios):
        raise ValueError("Each scenario must give a 0/1 overrun for every job")
    values = list(factory.prices_per_kwh) + [event.reward_dollars, event.penalty_dollars]
    places = max(0, max(-v.as_tuple().exponent for v in values))
    if places > 6:
        raise ValueError("At most six decimal places are supported")
    scale, n = 10**places, len(scenarios)
    prices = [int(p*scale) for p in factory.prices_per_kwh]
    reward, penalty = int(event.reward_dollars*scale), int(event.penalty_dollars*scale)
    power = {m.id: m.power_kw for m in factory.machines}
    model = cp_model.CpModel()
    candidates, objective = [], []
    occupancy = {(k,m.id,h): [] for k in range(n) for m in factory.machines for h in range(len(prices))}
    load = {(k,h): [] for k in range(n) for h in range(len(prices))}
    coefficient_budget = 0
    for job in factory.jobs:
        choices = []
        for machine in sorted(set(job.eligible_machines)):
            for start in range(job.release_hour, job.deadline_hour-job.duration_hours+1):
                ends = [start+job.duration_hours+d[job.id] for d in scenarios]
                if any(end > job.deadline_hour or any(o.machine_id == machine and start < o.end_hour
                        and o.start_hour < end for o in factory.outages) for end in ends):
                    continue
                x = model.new_bool_var(f"{job.id}_{machine}_{start}")
                a = Assignment(job.id,machine,start,start+job.duration_hours)
                candidates.append((x,a))
                choices.append(x)
                cost = sum(power[machine]*sum(prices[start:end]) for end in ends)
                coefficient_budget += abs(cost)
                objective.append(cost*x)
                for k,end in enumerate(ends):
                    for h in range(start,end):
                        occupancy[k,machine,h].append(x)
                        load[k,h].append(power[machine]*x)
        model.add(sum(choices)==1)
    for terms in occupancy.values():
        model.add(sum(terms)<=1)
    for k in range(n):
        for h,cap in enumerate(factory.power_caps_kw):
            if cap is not None:
                model.add(sum(load[k,h])<=cap)
        delivered = model.new_bool_var(f"delivered_{k}")
        for h in range(event.start_hour,event.end_hour):
            cap = reference_load[h]-event.reduction_kw
            model.add(sum(load[k,h])<=cap).only_enforce_if(delivered)
        objective.append(penalty-(reward+penalty)*delivered)
        coefficient_budget += reward+2*penalty
    if coefficient_budget >= 2**50:
        raise ValueError("Stochastic objective exceeds numeric budget")
    model.minimize(sum(objective))
    issue = model.validate()
    if issue:
        raise ValueError(issue)
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=time_limit
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=0
    status=solver.solve(model)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        return StochasticResult(solver.status_name(status),None,None,None,n,solver.wall_time)
    schedule=tuple(a for x,a in candidates if solver.value(x))
    if validate(factory,schedule):
        raise RuntimeError("Stochastic plan fails nominal production constraints")
    # Independently reconstruct every training scenario and its settlement.
    total=Decimal(0)
    for draw in scenarios:
        extended=tuple(Assignment(a.job_id,a.machine_id,a.start_hour,a.end_hour+draw[a.job_id]) for a in schedule)
        from dataclasses import replace
        changed=replace(factory,jobs=tuple(replace(j,duration_hours=j.duration_hours+draw[j.id]) for j in factory.jobs))
        from .scheduling import hourly_load_kw,energy_cost
        if validate(changed,extended):
            raise RuntimeError("SAA schedule violates a training scenario")
        actual_load=hourly_load_kw(changed,extended)
        delivered=all(actual_load[h]<=reference_load[h]-event.reduction_kw for h in range(event.start_hour,event.end_hour))
        total += energy_cost(changed,extended) + (-event.reward_dollars if delivered else event.penalty_dollars)
    if abs(float(total*scale)-solver.objective_value)>0.25:
        raise RuntimeError("Independent scenario settlement disagrees with SAA objective")
    return StochasticResult(solver.status_name(status),schedule,total/n,solver.best_objective_bound/(scale*n),n,solver.wall_time)
