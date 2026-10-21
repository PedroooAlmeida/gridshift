"""Seeded runtime stress simulation, not a calibrated real-world risk model."""
import random
from typing import Sequence
from .models import Assignment, Factory


def simulate(factory: Factory, schedule: Sequence[Assignment], trials=500,
             overrun_probability=0.15, seed=42):
    from .scheduling import validate
    if validate(factory, schedule):
        raise ValueError("Stress simulation requires a validated nominal schedule")
    if trials < 1 or not 0 <= overrun_probability <= 1:
        raise ValueError("Invalid simulation parameters")
    rng = random.Random(seed)
    jobs = {j.id: j for j in factory.jobs}
    powers = {m.id: m.power_kw for m in factory.machines}
    failures, late_trials, cap_trials = 0, 0, 0
    for _ in range(trials):
        load = {}
        late = False
        for machine in factory.machines:
            available = 0
            for a in sorted((a for a in schedule if a.machine_id == machine.id), key=lambda a: a.start_hour):
                start = max(a.start_hour, available)
                duration = jobs[a.job_id].duration_hours + (rng.random() < overrun_probability)
                # Non-preemptive execution waits out any outage that it intersects.
                while True:
                    hit = [o.end_hour for o in factory.outages if o.machine_id == machine.id
                           and start < o.end_hour and o.start_hour < start + duration]
                    if not hit:
                        break
                    start = max(hit)
                available = start + duration
                late |= available > jobs[a.job_id].deadline_hour
                for h in range(start, available):
                    load[h] = load.get(h, 0) + powers[machine.id]
        cap_fail = any(cap is not None and load.get(h, 0) > cap
                       for h, cap in enumerate(factory.power_caps_kw))
        late_trials += late
        cap_trials += cap_fail
        failures += late or cap_fail
    # Wilson interval communicates Monte Carlo sampling error, not model accuracy.
    rate = failures / trials
    z = 1.96
    center = (rate + z*z/(2*trials))/(1+z*z/trials)
    radius = z*((rate*(1-rate)/trials+z*z/(4*trials*trials))**0.5)/(1+z*z/trials)
    return {"trials": trials, "seed": seed, "overrun_probability": overrun_probability,
            "failure_rate": rate, "deadline_failure_rate": late_trials / trials,
            "cap_failure_rate": cap_trials / trials,
            "failure_rate_95pct_interval": [max(0, center-radius), min(1, center+radius)],
            "assumption": "Each job independently takes one extra hour with the stated probability; "
                          "fixed machine order, starts delayed as needed. Synthetic stress only."}
