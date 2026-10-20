from .scenarios import demo_factory
from .scheduling import fcfs, validate, energy_cost, hourly_load_kw


def main():
    factory = demo_factory()
    schedule = fcfs(factory)
    errors = validate(factory, schedule)
    print("GridShift | Phase 1 baseline | 3 machines, 15 jobs, 24 hours")
    print("Job      Machine   Start  End  Deadline")
    deadlines = {j.id: j.deadline_hour for j in factory.jobs}
    for a in schedule:
        print(f"{a.job_id:8} {a.machine_id:8} {a.start_hour:5} {a.end_hour:4} {deadlines[a.job_id]:9}")
    print(f"Validation errors: {len(errors)}")
    print(f"Energy: {sum(hourly_load_kw(factory, schedule))} kWh")
    print(f"Electricity cost: ${energy_cost(factory, schedule):.2f}")
    print("This is a heuristic baseline; no optimality or savings claim yet.")


if __name__ == "__main__":
    main()
