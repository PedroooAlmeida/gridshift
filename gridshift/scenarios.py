"""Fixed Phase 1 fixture: 3 machines, 15 jobs, 24 hourly prices."""
from decimal import Decimal
from .models import Factory, Job, Machine


def demo_factory() -> Factory:
    machines = (Machine("press", 50), Machine("mill", 30), Machine("oven", 80))
    jobs = tuple(
        Job("job-%02d" % (i + 1), 1 + i % 3, (i // 3) * 2,
            min(24, (i // 3) * 2 + 10),
            (machines[i % 3].id, machines[(i + 1) % 3].id))
        for i in range(15)
    )
    prices = tuple(Decimal(p) for p in (
        "0.06", "0.05", "0.05", "0.05", "0.06", "0.08",
        "0.10", "0.12", "0.14", "0.14", "0.12", "0.11",
        "0.10", "0.12", "0.16", "0.22", "0.35", "0.40",
        "0.32", "0.20", "0.14", "0.10", "0.08", "0.07"))
    return Factory(machines, jobs, prices)
