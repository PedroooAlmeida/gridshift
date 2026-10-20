"""Hours are integer boundaries; execution intervals are [start, end)."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple


@dataclass(frozen=True)
class Machine:
    id: str
    power_kw: int


@dataclass(frozen=True)
class Job:
    id: str
    duration_hours: int
    release_hour: int
    deadline_hour: int
    eligible_machines: Tuple[str, ...]


@dataclass(frozen=True)
class Factory:
    machines: Tuple[Machine, ...]
    jobs: Tuple[Job, ...]
    prices_per_kwh: Tuple[Decimal, ...]

    def __post_init__(self):
        machine_ids = [m.id for m in self.machines]
        job_ids = [j.id for j in self.jobs]
        if not machine_ids or len(set(machine_ids)) != len(machine_ids):
            raise ValueError("Machines must have unique IDs and cannot be empty")
        if len(set(job_ids)) != len(job_ids):
            raise ValueError("Jobs must have unique IDs")
        if any(not m.id or type(m.power_kw) is not int or m.power_kw <= 0 for m in self.machines):
            raise ValueError("Machine IDs and positive integer power are required")
        if not self.prices_per_kwh or any(
            not isinstance(p, Decimal) or not p.is_finite() for p in self.prices_per_kwh
        ):
            raise ValueError("Prices must be finite Decimal values (negative prices are allowed)")
        for j in self.jobs:
            if any(type(v) is not int for v in (j.duration_hours, j.release_hour, j.deadline_hour)):
                raise ValueError("Job times must be integer hours")
            if not j.id or j.duration_hours <= 0 or not 0 <= j.release_hour < j.deadline_hour <= len(self.prices_per_kwh):
                raise ValueError("Invalid job time window")
            if not j.eligible_machines or not set(j.eligible_machines) <= set(machine_ids):
                raise ValueError("Every job needs known eligible machines")
        # A well-formed input may still be infeasible; the scheduler must report that.


@dataclass(frozen=True)
class Assignment:
    job_id: str
    machine_id: str
    start_hour: int
    end_hour: int
