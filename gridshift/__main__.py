from .optimizer import optimize
from .scenarios import demo_factory
from .scheduling import energy_cost, fcfs, hourly_load_kw, validate


def show(factory, schedule):
    print("Job      Machine   Start  End  Deadline")
    deadlines = {j.id: j.deadline_hour for j in factory.jobs}
    for a in schedule:
        print(
            f"{a.job_id:8} {a.machine_id:8} {a.start_hour:5} {a.end_hour:4} {deadlines[a.job_id]:9}"
        )
    print(f"Validation errors: {len(validate(factory, schedule))}")
    print(f"Energy: {sum(hourly_load_kw(factory, schedule))} kWh")
    print(f"Electricity cost: ${energy_cost(factory, schedule):.2f}")


def main():
    factory = demo_factory()
    baseline = fcfs(factory)
    baseline_cost = energy_cost(factory, baseline)
    print("GridShift | 3 machines, 15 jobs, 24 hours\n\nFCFS baseline")
    show(factory, baseline)
    result = optimize(factory)
    print(f"\nCP-SAT status: {result.status} ({result.wall_time_seconds:.3f}s)")
    if result.schedule is None:
        print("No schedule returned; no cost or savings claimed.")
        return
    show(factory, result.schedule)
    print(f"Objective lower bound: ${result.lower_bound_dollars:.4f}")
    print(f"Absolute optimality gap: ${result.absolute_gap_dollars:.4f}")
    savings = baseline_cost - result.cost
    print(f"Savings vs baseline: ${savings:.2f} ({savings / baseline_cost:.1%})")
    print("Optimality applies to this discrete synthetic model and its assumptions.")


if __name__ == "__main__":
    main()
