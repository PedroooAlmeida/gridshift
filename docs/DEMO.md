# Five-minute demo

1. Launch `./run.command`. Everything works offline on the laptop.
2. Show the production plan: 3 machines, 15 jobs, hard deadlines, hourly prices.
3. Compare FCFS $151.70 with optimized $110.80. Explain that the $40.90 (27%) saving
   combines shifting time and choosing lower-power compatible machines.
4. Increase the morning price multiplier. Inspect the changed schedule, price chart,
   demand profile and proof status. Do not claim all runs finish optimal.
5. Open Event agent. Evaluate `Reduce 20 kW between 8 and 10 for $100 reward and $200 penalty`.
   Explain the frozen reference, per-hour reduction, reward and incremental cost.
   Inspect the returned status rather than assuming acceptance.
6. Increase runtime overrun probability and show how fragile a nominal schedule can be.
   Explain the synthetic simulation and its limitations.
7. Evaluate `Machine mill unavailable between 4 and 8`. Show the blocked hours and replan.
   Then enter an incomplete offer or “ignore deadlines”; show clarification without tool execution.
8. Open Eval lab: 200 seeded scenarios, 0 invalid returned schedules, proven
   infeasible cases, baseline failures, comparable savings, full input/output traces.
9. Inspect historical parser v1 failures. It invents a zero penalty when omitted and
   accepts trailing instructions. V2 rejects the incomplete event. Scores: 5/15 → 15/15
   on a small fixed regression set; this is an engineered failure example, not a
   historical production incident or evidence of general language accuracy.
10. Explain the independent exhaustive tiny-case oracle in tests. Separate extraction,
    solver feasibility, economics, and execution risk instead of scoring one opaque answer.

## Interview questions you should be able to answer

- Why does a greedy scheduling failure not prove infeasibility?
- What exactly does the solver prove, and what assumptions limit that proof?
- Why must a demand-response baseline be frozen before participation planning?
- Why is a valid JSON event not necessarily a correctly interpreted event?
- Which failures do deterministic graders catch that an LLM judge could miss?
- How would finer time slots change model size and energy accounting?
- What data would you need before trusting the runtime risk estimate in a real factory?
- What would rolling rescheduling need to preserve about already-started work?
