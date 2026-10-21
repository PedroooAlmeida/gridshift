"""Local dashboard: python -m streamlit run app.py"""
from dataclasses import asdict, replace
from decimal import Decimal
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gridshift.agent import EXAMPLES, run
from gridshift.optimizer import optimize
from gridshift.risk import simulate
from gridshift.scenarios import demo_factory
from gridshift.scheduling import energy_cost, fcfs, hourly_load_kw, validate
from gridshift.serialization import jsonable

st.set_page_config(page_title="GridShift · Factory control room", page_icon="⚡", layout="wide")
st.markdown('''<style>
.stApp {background: #0d141c; color: #e7edf4;}
.block-container {padding-top: 2rem; max-width: 1500px;}
h1 {letter-spacing: -2px; font-weight: 750 !important;}
[data-testid="stMetric"] {background:#15212d; padding:20px; border-radius:12px; border:1px solid #2a3946;}
[data-testid="stSidebar"] {background:#111c26;}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def plan(spike):
    f = demo_factory()
    prices = list(f.prices_per_kwh)
    for h in range(8, 11):
        prices[h] *= Decimal(str(spike))
    f = replace(f, prices_per_kwh=tuple(prices))
    return f, fcfs(f), optimize(f)


def timeline(factory, schedule, title):
    fig = go.Figure()
    colors = ["#52dec1", "#6aa9ff", "#c4a2ff"]
    machines = [m.id for m in factory.machines]
    deadlines = {j.id: j.deadline_hour for j in factory.jobs}
    for a in schedule:
        fig.add_trace(go.Bar(x=[a.end_hour-a.start_hour], y=[a.machine_id], base=[a.start_hour],
                            orientation="h", name=a.job_id, text=[a.job_id], textposition="inside",
                            marker_color=colors[machines.index(a.machine_id)],
                            hovertemplate=f"{a.job_id}<br>{a.machine_id}: {a.start_hour}:00–{a.end_hour}:00"
                                          f"<br>Deadline {deadlines[a.job_id]}:00<extra></extra>", showlegend=False))
    for o in factory.outages:
        fig.add_trace(go.Bar(x=[o.end_hour-o.start_hour], y=[o.machine_id], base=[o.start_hour],
                            orientation="h", marker_color="#ef7272", text=["OUTAGE"], showlegend=False))
    fig.update_layout(title=title, barmode="overlay", template="plotly_dark", height=240,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=15, r=15, t=45, b=20),
                      yaxis=dict(categoryorder="array", categoryarray=machines), xaxis=dict(range=[0,24], dtick=2, title="Hour of day"))
    return fig


with st.sidebar:
    st.markdown("### ⚡ GRIDSHIFT")
    st.caption("INDUSTRIAL ENERGY INTELLIGENCE")
    spike = st.slider("08:00–11:00 price multiplier", 1.0, 4.0, 1.0, 0.5)
    st.divider()
    st.markdown("**Factory assumptions**")
    st.caption("3 machines · 15 jobs · 24 hours\n\nNon-preemptive jobs. Hard deadlines. Constant active power. Zero idle power.")
    st.caption("All operations are simulated; no factory or utility actions are executed.")

st.caption("OPERATIONS / ENERGY / EVALUATION")
st.title("Make every kilowatt count.")
st.write("Shift production. Protect deadlines. Prove the decision.")
with st.spinner("Solving the factory schedule…"):
    factory, baseline, result = plan(spike)
base_cost = energy_cost(factory, baseline)
if result.schedule is None:
    st.error("Solver returned " + result.status + ". No optimized schedule available.")
    st.stop()
savings = base_cost - result.cost
cols = st.columns(4)
cols[0].metric("Baseline energy cost", f"${base_cost:.2f}")
cols[1].metric("Optimized energy cost", f"${result.cost:.2f}")
cols[2].metric("Operating savings", f"${savings:.2f}", f"{savings/base_cost:.1%}" if base_cost else None)
cols[3].metric("Constraint violations", len(validate(factory, result.schedule)))
st.caption(rf"Solver {result.status} · lower bound \${result.lower_bound_dollars:.2f} · "
           rf"absolute gap \${result.absolute_gap_dollars:.4f} · {result.wall_time_seconds:.2f}s")
operations, events, evaluation, engineering = st.tabs(["Production plan", "Event agent", "Eval lab", "Engineering"])
with operations:
    st.plotly_chart(timeline(factory, baseline, "01 / FCFS baseline"), use_container_width=True)
    st.plotly_chart(timeline(factory, result.schedule, "02 / Optimized production"), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Bar(x=list(range(24)), y=[float(p) for p in factory.prices_per_kwh], marker_color="#6aa9ff"))
        fig.update_layout(title="Hourly electricity price ($/kWh)", template="plotly_dark", height=280)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        for label, schedule in [("Baseline", baseline), ("Optimized", result.schedule)]:
            fig.add_trace(go.Scatter(x=list(range(25)), y=hourly_load_kw(factory, schedule) + (hourly_load_kw(factory, schedule)[-1],),
                                    name=label, mode="lines", line_shape="hv"))
        fig.update_layout(title="Factory demand (kW)", template="plotly_dark", height=280)
        st.plotly_chart(fig, use_container_width=True)
    st.info("Savings include time shifting and choosing lower-power eligible machines. "
            "This is a discrete synthetic model, not measured factory savings.")
    with st.expander("Jobs, deadlines and assignments"):
        st.dataframe(pd.DataFrame([asdict(j) for j in factory.jobs]), hide_index=True)
        st.dataframe(pd.DataFrame([asdict(a) for a in result.schedule]), hide_index=True)
    st.download_button("Download verified plan JSON", json.dumps(jsonable({"factory": factory, "baseline": baseline,
                       "optimized": result}), indent=2), "gridshift-plan.json", "application/json")
with events:
    st.subheader("From operational event to verified plan")
    st.write("Demand response is measured against a frozen, optimized reference plan. "
             "The reduction must hold in every event hour.")
    mode_label = st.selectbox("Event interpreter", ["Offline · strict grammar", "OpenAI · structured extraction"])
    mode = "offline" if mode_label.startswith("Offline") else "openai"
    if mode == "offline":
        st.caption("Offline mode is a deterministic parser, not an LLM. Use the examples exactly, changing their numbers.")
    else:
        st.caption("Sends your event text to OpenAI when you click Evaluate. Requires OPENAI_API_KEY in the server environment.")
    st.code("\n".join(EXAMPLES), language="text")
    text = st.text_area("Operational event", EXAMPLES[0])
    if st.button("Evaluate event", type="primary"):
        if mode == "openai" and not os.environ.get("OPENAI_API_KEY"):
            st.error("OPENAI_API_KEY is not configured. Offline mode remains available.")
        else:
            try:
                with st.spinner("Validating the event and calling planning tools…"):
                    st.session_state["decision"] = (spike, text, mode, run(factory, text, mode))
            except Exception as exc:
                st.session_state.pop("decision", None)
                st.error(f"Event evaluation failed ({type(exc).__name__}); no decision was made.")
    saved = st.session_state.get("decision")
    if saved and saved[:3] == (spike, text, mode):
        decision = saved[3]
        st.markdown("### " + decision.action)
        st.write(decision.explanation.replace("$", "\\$"))
        if decision.candidate and decision.candidate.schedule is not None:
            st.caption("Candidate schedule; a declined offer does not replace the operating plan.")
            st.plotly_chart(timeline(decision.factory, decision.candidate.schedule, "Event response candidate"), use_container_width=True)
            with st.expander("Runtime uncertainty stress test", expanded=True):
                p = st.slider("Chance each job takes one extra hour", 0.0, 0.5, 0.15, 0.05)
                stress = simulate(decision.factory, decision.candidate.schedule, overrun_probability=p)
                st.metric("Any deadline or power-cap failure", f"{stress['failure_rate']:.1%}")
                st.caption(stress["assumption"])
                st.json(stress)
                if decision.event.kind == "demand_response" and decision.net_benefit is not None:
                    q = Decimal(str(stress["cap_failure_rate"]))
                    incremental = decision.candidate.cost - decision.reference.cost
                    net = (1-q)*decision.event.reward_dollars - q*decision.event.penalty_dollars - incremental
                    st.caption(rf"Illustrative reward/penalty sensitivity: \${net:.2f} using nominal energy cost and "
                               "simulated cap failure frequency. Excludes delay penalties and realized energy costs; "
                               "not a stochastic-profit estimate or calibrated recommendation.")
        with st.expander("Structured event and tool trace"):
            st.json(jsonable(decision.event))
            st.json(jsonable(decision.trace))
        st.download_button("Download event trace", json.dumps(jsonable(decision), indent=2), "gridshift-trace.json", "application/json")
with evaluation:
    st.subheader("Reliability is a measurable property.")
    report_path = Path(__file__).parent / "evals/latest.json"
    if not report_path.exists():
        st.info("Run python -m gridshift.evaluate to generate the benchmark report.")
    else:
        report = json.loads(report_path.read_text())
        summary = report["summary"]
        a, b, c = st.columns(3)
        a.metric("Seeded scenarios", summary["scenarios"])
        b.metric("Invalid returned schedules", summary["invalid_schedules"])
        c.metric("Proven optimal", summary["status_counts"].get("OPTIMAL", 0))
        st.caption(report["description"])
        st.json(summary)
        st.markdown("#### Eval-driven repair: permissive parser → validated event boundary")
        st.write("The historical v1 parser accepted partial offers and invented a zero penalty. "
                 "The production v2 parser requires a complete, valid event or asks for clarification.")
        a,b = st.columns(2)
        a.metric("Historical v1 parser", f"{report['parser_v1']['passed']}/{report['parser_v1']['total']}")
        b.metric("Current v2 offline parser", f"{report['parser_v2']['passed']}/{report['parser_v2']['total']}")
        failures = [t for t in report["parser_v1"]["traces"] if not t["passed"]]
        if failures:
            selected = st.selectbox("Inspect a historical parser failure", range(len(failures)), format_func=lambda i: failures[i]["text"])
            st.json(failures[selected])
        st.markdown("#### Scenario traces")
        split = st.radio("Seed split", ["development", "heldout"], horizontal=True)
        cases = [c for c in report["cases"] if c["split"] == split]
        st.dataframe(pd.DataFrame([{"seed": c["seed"], "status": c["optimized"]["status"],
                                    "baseline_cost": c["baseline_cost"], "optimized_cost": c["optimized"]["cost"],
                                    "lower_bound_dollars": c["optimized"]["lower_bound_dollars"],
                                    "violations": len(c["validation_errors"])} for c in cases]), hide_index=True)
        selected_seed = st.selectbox("Inspect full scenario", [c["seed"] for c in cases])
        with st.expander("Inputs, schedules, bounds and failures"):
            st.json(next(c for c in cases if c["seed"] == selected_seed))
        st.download_button("Download eval report", report_path.read_text(), "gridshift-evals.json", "application/json")
with engineering:
    st.subheader("Explain the system in five minutes")
    st.markdown("""
1. **Model:** jobs, eligible machines, durations, deadlines, outages, hourly prices.
2. **Optimize:** choose one legal placement per job; enforce machine occupancy and site power limits.
3. **Verify:** independently reject missing jobs, overlaps, incompatible machines, outages, or late completion.
4. **Interpret:** typed event extraction dispatches to deterministic tools. The model cannot invent schedules or savings.
5. **Evaluate:** exhaustive tiny-instance oracles, seeded benchmarks, parser regressions, and runtime stress trials.

**Trust boundary:** event text → validated schema → planning tools → independently checked schedule → evidence-based explanation.

**Limitations:** one-hour resolution, fixed active power, no setup times, no dependencies,
no live ERP or utility integration. Outages are known before replanning starts; this is
not mid-execution rescheduling. The stress model is synthetic and independent across jobs.
OpenAI integration is optional; offline eval scores do not measure LLM performance.
""")
