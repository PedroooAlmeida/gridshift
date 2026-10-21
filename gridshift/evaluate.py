"""Reproducible offline evaluations with per-case inputs, outputs and failures."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
from importlib import resources
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
from decimal import Decimal

from .agent import parse_offline
from .grading import grade_event, regression_failures
from .optimizer import optimize
from .scenarios import seeded_factory
from .scheduling import BaselineFailure, energy_cost, fcfs, validate, price_aware_greedy
from .serialization import jsonable

ROOT = Path(__file__).resolve().parents[1]


def legacy_parse(text):
    """Quarantined flawed v1: accepts partial offers and invents a zero penalty."""
    match = re.match(r"Reduce (\d+) kW between (\d+) and (\d+) for \$(\d+) reward", text, re.I)
    if match:
        reduction, start, end, reward = map(int, match.groups())
        penalty = re.search(r"and \$(\d+) penalty", text)
        return {"kind": "demand_response", "reduction_kw": reduction, "start_hour": start,
                "end_hour": end, "reward_dollars": str(reward),
                "penalty_dollars": penalty.group(1) if penalty else "0"}
    return {"kind": "clarify", "clarification": "Unrecognized event"}


def parser_evals(parser=None, dataset="offline_events.json"):
    cases = json.loads(resources.files("gridshift.data").joinpath(dataset).read_text())
    traces = []
    for case in cases:
        try:
            actual = parse_offline(case["text"]).model_dump(mode="json") if parser is None else parser(case["text"])
            passed = grade_event(actual, case["expected"])
        except Exception as exc:
            actual, passed = {"error": type(exc).__name__}, False
        traces.append({**case, "actual": actual, "passed": passed})
    return {"passed": sum(t["passed"] for t in traces), "total": len(traces), "traces": traces}


def evaluate(count=200, start_seed=0, time_limit=1.0):
    if count < 1 or count > 10000:
        raise ValueError("Count must be 1–10000")
    cases = []
    for i in range(count):
        split = "development" if i < (count + 1) // 2 else "heldout"
        seed = start_seed + i if split == "development" else 10000 + start_seed + i
        f = seeded_factory(seed)
        try:
            baseline = fcfs(f)
            baseline_cost = energy_cost(f, baseline)
        except BaselineFailure:
            baseline, baseline_cost = None, None
        try:
            greedy = price_aware_greedy(f)
            greedy_cost = energy_cost(f, greedy)
        except BaselineFailure:
            greedy, greedy_cost = None, None
        result = optimize(f, time_limit)
        errors = validate(f, result.schedule) if result.schedule is not None else ()
        # Deliberately injected accounting defect: bills all execution at the start-hour price.
        legacy_cost = None
        if baseline is not None:
            power = {m.id: m.power_kw for m in f.machines}
            legacy_cost = sum((power[a.machine_id] * (a.end_hour-a.start_hour) *
                               f.prices_per_kwh[a.start_hour] for a in baseline), Decimal(0))
        independent_cost = None
        if baseline is not None:
            independent_cost = sum((next(m.power_kw for m in f.machines if m.id == a.machine_id)
                                    * f.prices_per_kwh[h] for a in baseline
                                    for h in range(a.start_hour, a.end_hour)), Decimal(0))
        optimized_cost = None
        if result.schedule is not None:
            optimized_cost = sum((next(m.power_kw for m in f.machines if m.id == a.machine_id)
                                  * f.prices_per_kwh[h] for a in result.schedule
                                  for h in range(a.start_hour, a.end_hour)), Decimal(0))
        cases.append({"seed": seed, "split": split, "factory": jsonable(f),
                      "price_aware_schedule": jsonable(greedy), "price_aware_cost": jsonable(greedy_cost),
                      "baseline_schedule": jsonable(baseline), "baseline_cost": jsonable(baseline_cost),
                      "optimized": jsonable(result), "validation_errors": errors,
                      "legacy_cost": jsonable(legacy_cost),
                      "legacy_cost_correct": legacy_cost == baseline_cost if baseline is not None else None,
                      "fixed_cost_correct": independent_cost == baseline_cost if baseline is not None else None,
                      "optimized_cost_correct": optimized_cost == result.cost if result.schedule is not None else None})
    costs = [float(Decimal(c["baseline_cost"]) - Decimal(c["optimized"]["cost"])) for c in cases
             if c["baseline_cost"] is not None and c["optimized"]["cost"] is not None]
    status = Counter(c["optimized"]["status"] for c in cases)
    comparable = [c for c in cases if c["baseline_cost"] is not None and c["optimized"]["cost"] is not None]
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision, dirty = "unknown", True
    summary = {"scenarios": count, "status_counts": dict(status),
               "returned_schedules": sum(c["optimized"]["schedule"] is not None for c in cases),
               "invalid_schedules": sum(bool(c["validation_errors"]) for c in cases),
               "baseline_failures": sum(c["baseline_schedule"] is None for c in cases),
               "comparable_cases": len(comparable),
               "optimized_no_worse_than_baseline": sum(Decimal(c["optimized"]["cost"]) <= Decimal(c["baseline_cost"]) for c in comparable),
               "mean_savings_dollars_on_comparable": statistics.mean(costs) if costs else None,
               "legacy_accounting_failures": sum(c["legacy_cost_correct"] is False for c in cases),
               "fixed_accounting_failures": sum(c["fixed_cost_correct"] is False for c in cases),
               "p95_solver_seconds": sorted(c["optimized"]["wall_time_seconds"] for c in cases)[min(count-1, int(count*.95))]}
    greedy_comparable = [c for c in cases if c["price_aware_cost"] is not None and c["optimized"]["cost"] is not None]
    summary["price_aware_comparable"] = len(greedy_comparable)
    summary["price_aware_failures"] = sum(c["price_aware_schedule"] is None for c in cases)
    summary["mean_savings_vs_price_aware"] = statistics.mean(
        float(Decimal(c["price_aware_cost"])-Decimal(c["optimized"]["cost"])) for c in greedy_comparable) if greedy_comparable else None
    summary["split_status_counts"] = {
        split: dict(Counter(c["optimized"]["status"] for c in cases if c["split"] == split))
        for split in ("development", "heldout")}
    summary["known_infeasibility_misses"] = sum(
        c["seed"] % 11 == 0 and c["optimized"]["status"] != "INFEASIBLE" for c in cases)
    report = {"schema_version": 2, "created_utc": datetime.now(timezone.utc).isoformat(),
            "revision": revision, "working_tree_dirty": dirty,
            "ortools": importlib.metadata.version("ortools"), "solver_limit_seconds": time_limit,
            "description": "Synthetic offline benchmark; heldout seeds are reserved, not independent external data. "
                           "Parser scores are strict-grammar scores, not LLM scores. No real-world savings inferred.",
            "summary": summary, "parser_v1": parser_evals(legacy_parse), "parser_v2": parser_evals(),
            "cases": cases}
    corpus = [{"seed": c["seed"], "factory": c["factory"]} for c in cases]
    sources = sorted((ROOT / "gridshift").rglob("*.py"))
    if (ROOT / "app.py").exists():
        sources.append(ROOT / "app.py")
    report["source_sha256"] = hashlib.sha256(b"".join(
        str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() for path in sources)).hexdigest()
    report["dataset_sha256"] = hashlib.sha256(json.dumps(corpus, sort_keys=True).encode()).hexdigest()
    report["regression_failures"] = regression_failures(report)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=200)
    p.add_argument("--start-seed", type=int, default=0)
    p.add_argument("--time-limit", type=float, default=1.0)
    p.add_argument("--output", type=Path, default=Path.cwd() / "evals/latest.json")
    args = p.parse_args()
    report = evaluate(args.count, args.start_seed, args.time_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"Parser v1: {report['parser_v1']['passed']}/{report['parser_v1']['total']}; "
          f"v2: {report['parser_v2']['passed']}/{report['parser_v2']['total']}")
    # Regression gate excludes baseline heuristic failures and honest timeouts.
    if report["regression_failures"]:
        print(json.dumps(report["regression_failures"], indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
