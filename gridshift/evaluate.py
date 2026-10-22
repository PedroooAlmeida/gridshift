"""Seeded scheduling benchmarks and event-extraction regression cases."""

import argparse
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from importlib import metadata, resources
from pathlib import Path

from .agent import parse_offline
from .grading import grade_event, regression_failures
from .models import Assignment, Factory
from .optimizer import optimize
from .scenarios import seeded_factory
from .scheduling import BaselineFailure, energy_cost, fcfs, price_aware_greedy, validate
from .serialization import jsonable

ROOT = Path(__file__).resolve().parents[1]


def parser_evals(parser=None, dataset: str = "offline_events.json") -> dict:
    cases = json.loads(resources.files("gridshift.data").joinpath(dataset).read_text())
    traces = []
    for case in cases:
        try:
            actual = (
                parse_offline(case["text"]).model_dump(mode="json")
                if parser is None
                else parser(case["text"])
            )
            passed = grade_event(actual, case["expected"])
        except Exception as exc:
            # Persist the failure class, not SDK messages that may contain request details.
            actual, passed = {"error": type(exc).__name__}, False
        traces.append({**case, "actual": actual, "passed": passed})
    return {"passed": sum(t["passed"] for t in traces), "total": len(traces), "traces": traces}


def _assignment_cost(factory: Factory, schedule: tuple[Assignment, ...]) -> Decimal:
    """Independent per-assignment accounting; do not reuse the hourly-load accountant."""
    power = {machine.id: machine.power_kw for machine in factory.machines}
    return sum(
        (
            power[a.machine_id] * factory.prices_per_kwh[hour]
            for a in schedule
            for hour in range(a.start_hour, a.end_hour)
        ),
        Decimal(0),
    )


def _run_baseline(factory: Factory, scheduler):
    try:
        schedule = scheduler(factory)
        return schedule, energy_cost(factory, schedule)
    except BaselineFailure:
        return None, None


def _evaluate_case(seed: int, split: str, time_limit: float) -> dict:
    factory = seeded_factory(seed)
    baseline, baseline_cost = _run_baseline(factory, fcfs)
    greedy, greedy_cost = _run_baseline(factory, price_aware_greedy)
    result = optimize(factory, time_limit)
    return {
        "seed": seed,
        "split": split,
        "factory": jsonable(factory),
        "baseline_schedule": jsonable(baseline),
        "baseline_cost": jsonable(baseline_cost),
        "price_aware_schedule": jsonable(greedy),
        "price_aware_cost": jsonable(greedy_cost),
        "optimized": jsonable(result),
        "validation_errors": validate(factory, result.schedule)
        if result.schedule is not None
        else (),
        "baseline_cost_correct": (
            _assignment_cost(factory, baseline) == baseline_cost if baseline is not None else None
        ),
        "optimized_cost_correct": (
            _assignment_cost(factory, result.schedule) == result.cost
            if result.schedule is not None
            else None
        ),
    }


def _comparable_cases(cases: list[dict], cost_key: str) -> list[dict]:
    return [
        case
        for case in cases
        if case[cost_key] is not None and case["optimized"]["cost"] is not None
    ]


def _mean_savings(cases: list[dict], cost_key: str):
    return (
        statistics.mean(
            float(Decimal(case[cost_key]) - Decimal(case["optimized"]["cost"])) for case in cases
        )
        if cases
        else None
    )


def _summarize(cases: list[dict]) -> dict:
    comparable = _comparable_cases(cases, "baseline_cost")
    greedy_comparable = _comparable_cases(cases, "price_aware_cost")
    solver_times = sorted(case["optimized"]["wall_time_seconds"] for case in cases)
    return {
        "scenarios": len(cases),
        "status_counts": dict(Counter(c["optimized"]["status"] for c in cases)),
        "returned_schedules": sum(c["optimized"]["schedule"] is not None for c in cases),
        "invalid_schedules": sum(bool(c["validation_errors"]) for c in cases),
        "baseline_failures": sum(c["baseline_schedule"] is None for c in cases),
        "comparable_cases": len(comparable),
        "optimized_no_worse_than_baseline": sum(
            Decimal(c["optimized"]["cost"]) <= Decimal(c["baseline_cost"]) for c in comparable
        ),
        "mean_savings_dollars_on_comparable": _mean_savings(comparable, "baseline_cost"),
        "baseline_accounting_failures": sum(c["baseline_cost_correct"] is False for c in cases),
        "optimized_accounting_failures": sum(c["optimized_cost_correct"] is False for c in cases),
        "p95_solver_seconds": solver_times[min(len(cases) - 1, int(len(cases) * 0.95))],
        "price_aware_comparable": len(greedy_comparable),
        "price_aware_failures": sum(c["price_aware_schedule"] is None for c in cases),
        "mean_savings_vs_price_aware": _mean_savings(greedy_comparable, "price_aware_cost"),
        "split_status_counts": {
            split: dict(Counter(c["optimized"]["status"] for c in cases if c["split"] == split))
            for split in ("development", "heldout")
        },
        "known_infeasibility_misses": sum(
            c["seed"] % 11 == 0 and c["optimized"]["status"] != "INFEASIBLE" for c in cases
        ),
    }


def _source_provenance() -> dict:
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision, dirty = "unknown", True
    sources = sorted((ROOT / "gridshift").rglob("*.py"))
    if (ROOT / "app.py").exists():
        sources.append(ROOT / "app.py")
    source_hash = hashlib.sha256(
        b"".join(
            str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() for path in sources
        )
    ).hexdigest()
    return {"revision": revision, "working_tree_dirty": dirty, "source_sha256": source_hash}


def evaluate(count: int = 200, start_seed: int = 0, time_limit: float = 1.0) -> dict:
    if not 1 <= count <= 10000:
        raise ValueError("Count must be 1–10000")
    cases = []
    for index in range(count):
        split = "development" if index < (count + 1) // 2 else "heldout"
        seed = start_seed + index if split == "development" else 10000 + start_seed + index
        cases.append(_evaluate_case(seed, split, time_limit))
    corpus = [{"seed": c["seed"], "factory": c["factory"]} for c in cases]
    report = {
        "schema_version": 3,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **_source_provenance(),
        "dataset_sha256": hashlib.sha256(json.dumps(corpus, sort_keys=True).encode()).hexdigest(),
        "ortools": metadata.version("ortools"),
        "solver_limit_seconds": time_limit,
        "description": "Synthetic scheduling benchmark with separate development and heldout seeds. "
        "Event extraction scores cover the offline grammar only.",
        "summary": _summarize(cases),
        "event_extraction": parser_evals(),
        "cases": cases,
    }
    report["regression_failures"] = regression_failures(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--time-limit", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path.cwd() / "evals/latest.json")
    args = parser.parse_args()
    report = evaluate(args.count, args.start_seed, args.time_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    extraction = report["event_extraction"]
    print(f"Offline extraction: {extraction['passed']}/{extraction['total']}")
    if report["regression_failures"]:
        print(json.dumps(report["regression_failures"], indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
