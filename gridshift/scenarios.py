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


def seeded_factory(seed: int) -> Factory:
    """Compact diverse benchmark; some inputs are intentionally infeasible."""
    import random
    from dataclasses import replace
    from .models import Outage
    rng = random.Random(seed)
    machines = tuple(Machine("m" + str(i), rng.choice((20, 40, 60))) for i in range(3))
    jobs = tuple(Job("j" + str(i), rng.randint(1, 3), rng.randint(0, 3),
                     rng.randint(6, 12), tuple(m.id for m in rng.sample(list(machines), rng.randint(1, 3))))
                 for i in range(8))
    prices = tuple(Decimal(rng.randint(-3, 40)) / 100 for _ in range(12))
    factory = Factory(machines, jobs, prices)
    if seed % 5 == 0:
        factory = replace(factory, outages=(Outage("m0", 2, 6),))
    if seed % 7 == 0:
        factory = replace(factory, power_caps_kw=tuple(80 if 4 <= h < 8 else None for h in range(12)))
    if seed % 11 == 0:
        factory = replace(factory, jobs=factory.jobs + tuple(
            Job("impossible" + str(i), 3, 0, 3, ("m0",)) for i in range(2)))
    return factory
