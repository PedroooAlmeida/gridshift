"""Fit runtime risk from binary observations; validate on synthetic held-out outcomes.

This is a reproducible calibration experiment, not evidence about real factories.
Training observations, probability-estimation draws, and test outcomes are disjoint.
"""
import argparse
import json
from pathlib import Path
import random
import statistics

from .agent import EXAMPLES, execute, parse_offline
from .risk import realize, runtime_draws, wilson
from .scenarios import demo_factory


def fit_overrun_probability(observations):
    observations = list(observations)
    if not observations or any(type(x) is not int or x not in (0, 1) for x in observations):
        raise ValueError("Supply nonempty binary runtime-overrun observations")
    count = sum(observations)
    return {"observations": len(observations), "overruns": count,
            "probability": (count+1)/(len(observations)+2),
            "frequency_95pct_interval": wilson(count, len(observations)),
            "estimator": "Beta(1,1) posterior mean for independent Bernoulli overruns"}


def failure_outcomes(factory, schedule, probability, seed, trials):
    outcomes = []
    for draw in runtime_draws(factory, trials, probability, seed):
        actual = realize(factory, schedule, draw)
        outcomes.append(int(actual["late"] or actual["cap_fail"]))
    return outcomes


def evaluate_calibration():
    factory = demo_factory()
    decision = execute(factory, parse_offline(EXAMPLES[0]))
    schedule, factory = decision.candidate.schedule, decision.factory
    if schedule is None:
        raise RuntimeError("Calibration fixture requires a feasible nominal plan")
    baseline_probability = statistics.mean(failure_outcomes(factory, schedule, .15, 901, 2000))
    cases = []
    for index in range(18):
        truth = .02 + .025*index
        rng = random.Random(2000+index)
        fitted = fit_overrun_probability(int(rng.random()<truth) for _ in range(400))
        predicted = statistics.mean(failure_outcomes(factory, schedule, fitted["probability"], 3000+index, 1000))
        outcomes = failure_outcomes(factory, schedule, truth, 4000+index, 400)
        cases.append({"regime": index, "synthetic_true_overrun_probability": truth, "fit": fitted,
                      "predicted_failure_probability": predicted, "test_trials": len(outcomes),
                      "test_failures": sum(outcomes), "observed_failure_rate": statistics.mean(outcomes),
                      "observed_rate_95pct_interval": wilson(sum(outcomes), len(outcomes)),
                      "brier_fitted": statistics.mean((predicted-y)**2 for y in outcomes),
                      "brier_fixed_prior": statistics.mean((baseline_probability-y)**2 for y in outcomes)})
    bins = []
    for i in range(10):
        subset = [c for c in cases if min(9, int(10*c["predicted_failure_probability"])) == i]
        if subset:
            bins.append({"bin": i, "regimes": len(subset), "test_trials": sum(c["test_trials"] for c in subset),
                         "predicted": statistics.mean(c["predicted_failure_probability"] for c in subset),
                         "observed": statistics.mean(c["observed_failure_rate"] for c in subset)})
    return {"schema_version": 1, "data_source": "synthetic", "regimes": len(cases),
            "training_observations": 400*len(cases), "heldout_trials": 400*len(cases),
            "brier_fitted": statistics.mean(c["brier_fitted"] for c in cases),
            "brier_fixed_prior": statistics.mean(c["brier_fixed_prior"] for c in cases),
            "expected_calibration_error": sum(b["regimes"]*abs(b["predicted"]-b["observed"]) for b in bins)/len(cases),
            "fixed_prior_overrun_probability": .15, "reliability_bins": bins, "cases": cases,
            "seeds": {"training": "2000..2017", "prediction": "3000..3017", "heldout": "4000..4017", "baseline": 901},
            "limitations": "Synthetic independent Bernoulli runtimes, same fixed schedule across regimes. "
                            "Brier is computed on individual heldout outcomes; ECE uses ten fixed bins. "
                            "Sampling intervals exclude model misspecification. No real-world calibration is claimed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path.cwd()/"evals/calibration.json")
    args = parser.parse_args()
    report = evaluate_calibration()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ("cases", "reliability_bins")}, indent=2))


if __name__ == "__main__":
    main()
