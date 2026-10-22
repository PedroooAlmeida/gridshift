"""A deliberately simple baseline, independent validator, and cost accounting."""

from decimal import Decimal
from typing import Sequence, Tuple

from .models import Assignment, Factory


class BaselineFailure(ValueError):
    """Greedy scheduling failed; this does NOT prove the factory is infeasible."""


def fcfs(factory: Factory) -> Tuple[Assignment, ...]:
    """Process by release time then input order; choose earliest append-only finish.

    Ties use machine ID. This heuristic neither backtracks nor fills earlier gaps.
    """
    available = {m.id: 0 for m in factory.machines}
    result = []
    for job in sorted(factory.jobs, key=lambda j: j.release_hour):
        options = []
        load = [0] * len(factory.prices_per_kwh)
        powers = {m.id: m.power_kw for m in factory.machines}
        for a in result:
            for h in range(a.start_hour, a.end_hour):
                load[h] += powers[a.machine_id]
        for m in job.eligible_machines:
            for start in range(
                max(available[m], job.release_hour), job.deadline_hour - job.duration_hours + 1
            ):
                end = start + job.duration_hours
                if any(
                    o.machine_id == m and start < o.end_hour and o.start_hour < end
                    for o in factory.outages
                ):
                    continue
                if factory.power_caps_kw and any(
                    factory.power_caps_kw[h] is not None
                    and load[h] + powers[m] > factory.power_caps_kw[h]
                    for h in range(start, end)
                ):
                    continue
                options.append((end, m, start))
                break
        if not options:
            raise BaselineFailure("Baseline could not place " + job.id)
        end, machine, start = min(options)
        result.append(Assignment(job.id, machine, start, end))
        available[machine] = end
    return tuple(result)


def validate(factory: Factory, schedule: Sequence[Assignment]) -> Tuple[str, ...]:
    """Check every required job and all constraints without trusting the scheduler."""
    jobs = {j.id: j for j in factory.jobs}
    machines = {m.id for m in factory.machines}
    seen = set()
    errors = []
    valid_intervals = []
    for a in schedule:
        if a.job_id in seen:
            errors.append("duplicate job: " + a.job_id)
        seen.add(a.job_id)
        if a.job_id not in jobs:
            errors.append("unknown job: " + a.job_id)
            continue
        j = jobs[a.job_id]
        if a.machine_id not in machines or a.machine_id not in j.eligible_machines:
            errors.append("incompatible machine: " + a.job_id)
        if type(a.start_hour) is not int or type(a.end_hour) is not int:
            errors.append("noninteger times: " + a.job_id)
            continue
        if a.end_hour - a.start_hour != j.duration_hours:
            errors.append("wrong duration: " + a.job_id)
        if not 0 <= a.start_hour < a.end_hour <= len(factory.prices_per_kwh):
            errors.append("outside horizon: " + a.job_id)
        if a.start_hour < j.release_hour or a.end_hour > j.deadline_hour:
            errors.append("release/deadline violation: " + a.job_id)
        if any(
            o.machine_id == a.machine_id and a.start_hour < o.end_hour and o.start_hour < a.end_hour
            for o in factory.outages
        ):
            errors.append("outage violation: " + a.job_id)
        valid_intervals.append(a)
    for job_id in sorted(set(jobs) - seen):
        errors.append("missing job: " + job_id)
    for i, a in enumerate(valid_intervals):
        for b in valid_intervals[i + 1 :]:
            if a.machine_id == b.machine_id and max(a.start_hour, b.start_hour) < min(
                a.end_hour, b.end_hour
            ):
                errors.append("machine overlap: " + a.job_id + "/" + b.job_id)
    if factory.power_caps_kw:
        powers = {m.id: m.power_kw for m in factory.machines}
        for h, cap in enumerate(factory.power_caps_kw):
            load = sum(
                powers.get(a.machine_id, 0)
                for a in valid_intervals
                if a.start_hour <= h < a.end_hour
            )
            if cap is not None and load > cap:
                errors.append("power cap violation at hour " + str(h))
    return tuple(errors)


def hourly_load_kw(factory: Factory, schedule: Sequence[Assignment]) -> Tuple[int, ...]:
    errors = validate(factory, schedule)
    if errors:
        raise ValueError("Invalid schedule: " + "; ".join(errors))
    power = {m.id: m.power_kw for m in factory.machines}
    load = [0] * len(factory.prices_per_kwh)
    for a in schedule:
        for hour in range(a.start_hour, a.end_hour):
            load[hour] += power[a.machine_id]
    return tuple(load)


def energy_cost(factory: Factory, schedule: Sequence[Assignment]) -> Decimal:
    # Each slot is one hour: kW × 1 h × $/kWh = dollars.
    return sum(
        (
            kw * price
            for kw, price in zip(hourly_load_kw(factory, schedule), factory.prices_per_kwh)
        ),
        Decimal("0"),
    )


def price_aware_greedy(factory: Factory) -> Tuple[Assignment, ...]:
    """Deadline-ordered greedy placement: cheapest legal machine/start each step.

    Stronger comparator than arbitrary FCFS ties; no backtracking or optimality claim.
    """
    result = []
    occupied = set()
    load = [0] * len(factory.prices_per_kwh)
    power = {m.id: m.power_kw for m in factory.machines}
    for job in sorted(factory.jobs, key=lambda j: (j.deadline_hour, j.release_hour, j.id)):
        choices = []
        for machine in job.eligible_machines:
            for start in range(job.release_hour, job.deadline_hour - job.duration_hours + 1):
                end = start + job.duration_hours
                if any((machine, h) in occupied for h in range(start, end)):
                    continue
                if any(
                    o.machine_id == machine and start < o.end_hour and o.start_hour < end
                    for o in factory.outages
                ):
                    continue
                if factory.power_caps_kw and any(
                    factory.power_caps_kw[h] is not None
                    and load[h] + power[machine] > factory.power_caps_kw[h]
                    for h in range(start, end)
                ):
                    continue
                cost = power[machine] * sum(factory.prices_per_kwh[start:end], Decimal(0))
                choices.append((cost, end, machine, start))
        if not choices:
            raise BaselineFailure("Price-aware greedy could not place " + job.id)
        _, end, machine, start = min(choices)
        result.append(Assignment(job.id, machine, start, end))
        for h in range(start, end):
            occupied.add((machine, h))
            load[h] += power[machine]
    return tuple(result)
