"""Local dashboard: python -m streamlit run app.py"""

import json
import os
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gridshift.agent import EXAMPLES, run
from gridshift.comparison import savings_ablation
from gridshift.optimizer import optimize
from gridshift.risk import simulate
from gridshift.scenarios import demo_factory
from gridshift.scheduling import energy_cost, fcfs, hourly_load_kw, validate
from gridshift.serialization import jsonable

st.set_page_config(page_title="GridShift · Factory control room", page_icon="⚡", layout="wide")
st.markdown(
    """<style>
.stApp {background: #0d141c; color: #e7edf4;}
.block-container {padding-top: 2rem; max-width: 1500px;}
h1 {letter-spacing: -2px; font-weight: 750 !important;}
[data-testid="stMetric"] {background:#15212d; padding:20px; border-radius:12px; border:1px solid #2a3946;}
[data-testid="stSidebar"] {background:#111c26;}
@media (max-width: 900px) {
  [data-testid="stMetric"] {padding:12px;}
  [data-testid="stMetricValue"] {font-size:1.35rem;}
  [data-testid="stMetricLabel"] p {font-size:0.75rem; white-space:normal;}
}
</style>""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def plan(spike):
    f = demo_factory()
    prices = list(f.prices_per_kwh)
    for h in range(8, 11):
        prices[h] *= Decimal(str(spike))
    f = replace(f, prices_per_kwh=tuple(prices))
    return f, fcfs(f), optimize(f)


@st.cache_data(show_spinner=False)
def ablation(spike):
    f, _, result = plan(spike)
    return savings_ablation(f, result)


def timeline(factory, schedule, title):
    fig = go.Figure()
    colors = ["#52dec1", "#6aa9ff", "#c4a2ff"]
    machines = [m.id for m in factory.machines]
    deadlines = {j.id: j.deadline_hour for j in factory.jobs}
    for a in schedule:
        fig.add_trace(
            go.Bar(
                x=[a.end_hour - a.start_hour],
                y=[a.machine_id],
                base=[a.start_hour],
                orientation="h",
                name=a.job_id,
                text=[a.job_id],
                textposition="inside",
                marker_color=colors[machines.index(a.machine_id)],
                hovertemplate=f"{a.job_id}<br>{a.machine_id}: {a.start_hour}:00–{a.end_hour}:00"
                f"<br>Deadline {deadlines[a.job_id]}:00<extra></extra>",
                showlegend=False,
            )
        )
    for o in factory.outages:
        fig.add_trace(
            go.Bar(
                x=[o.end_hour - o.start_hour],
                y=[o.machine_id],
                base=[o.start_hour],
                orientation="h",
                marker_color="#ef7272",
                text=["OUTAGE"],
                showlegend=False,
            )
        )
    fig.update_layout(
        title=title,
        barmode="overlay",
        template="plotly_dark",
        height=240,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=15, r=15, t=45, b=20),
        yaxis=dict(categoryorder="array", categoryarray=machines),
        xaxis=dict(range=[0, 24], dtick=2, title="Hour of day"),
    )
    return fig


with st.sidebar:
    st.markdown("### ⚡ GRIDSHIFT")
    st.caption("FACTORY SCHEDULING")
    spike = st.slider("08:00–11:00 price multiplier", 1.0, 4.0, 1.0, 0.5)
    st.divider()
    st.markdown("**Factory assumptions**")
    st.caption(
        "3 machines · 15 jobs · 24 hours\n\nNon-preemptive jobs. Hard deadlines. Constant active power. Zero idle power."
    )
    st.caption("All operations are simulated; no factory or utility actions are executed.")

st.caption("OPERATIONS / ENERGY / EVALUATION")
st.title("GridShift")
st.write("Production scheduling under electricity-price and runtime uncertainty.")
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
cols[2].metric(
    "Operating savings", f"${savings:.2f}", f"{savings / base_cost:.1%}" if base_cost else None
)
cols[3].metric("Constraint violations", len(validate(factory, result.schedule)))
st.caption(
    rf"Solver {result.status} · lower bound \${result.lower_bound_dollars:.2f} · "
    rf"absolute gap \${result.absolute_gap_dollars:.4f} · {result.wall_time_seconds:.2f}s"
)
operations, events, evaluation, engineering = st.tabs(
    ["Production plan", "Event agent", "Eval lab", "Engineering"]
)
with operations:
    st.plotly_chart(timeline(factory, baseline, "01 / FCFS baseline"), use_container_width=True)
    st.plotly_chart(
        timeline(factory, result.schedule, "02 / Optimized production"), use_container_width=True
    )
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(
            go.Bar(
                x=list(range(24)),
                y=[float(p) for p in factory.prices_per_kwh],
                marker_color="#6aa9ff",
            )
        )
        fig.update_layout(
            title="Hourly electricity price ($/kWh)", template="plotly_dark", height=280
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        for label, schedule in [("Baseline", baseline), ("Optimized", result.schedule)]:
            fig.add_trace(
                go.Scatter(
                    x=list(range(25)),
                    y=hourly_load_kw(factory, schedule) + (hourly_load_kw(factory, schedule)[-1],),
                    name=label,
                    mode="lines",
                    line_shape="hv",
                )
            )
        fig.update_layout(title="Factory demand (kW)", template="plotly_dark", height=280)
        st.plotly_chart(fig, use_container_width=True)
    st.info(
        "Savings include time shifting and choosing lower-power eligible machines. "
        "This is a discrete synthetic model, not measured factory savings."
    )
    with st.expander("Separate time shifting from machine choice"):
        attribution = ablation(spike)
        st.json(jsonable(attribution))
    with st.expander("Jobs, deadlines and assignments"):
        st.dataframe(pd.DataFrame([asdict(j) for j in factory.jobs]), hide_index=True)
        st.dataframe(pd.DataFrame([asdict(a) for a in result.schedule]), hide_index=True)
    st.download_button(
        "Download verified plan JSON",
        json.dumps(
            jsonable({"factory": factory, "baseline": baseline, "optimized": result}), indent=2
        ),
        "gridshift-plan.json",
        "application/json",
    )
with events:
    st.subheader("Event planning")
    st.write(
        "Demand response is measured against a frozen, optimized reference plan. "
        "The reduction must hold in every event hour."
    )
    mode_label = st.selectbox(
        "Event interpreter",
        [
            "Offline · strict grammar",
            "Anthropic Claude · tool extraction",
            "OpenAI · structured extraction",
        ],
    )
    mode = (
        "offline"
        if mode_label.startswith("Offline")
        else ("anthropic" if mode_label.startswith("Anthropic") else "openai")
    )
    api_key = None
    if mode == "anthropic":
        api_key = st.text_input(
            "Anthropic API key",
            type="password",
            key="anthropic_api_key",
            help="Used only in this local session. Never saved to disk, traces, or GitHub.",
        )
        st.caption(
            "The key and event text are sent only to Anthropic when you click Evaluate event."
        )
    if mode == "offline":
        st.caption(
            "Offline mode is a deterministic parser, not an LLM. Use the examples exactly, changing their numbers."
        )
    elif mode == "openai":
        st.caption(
            "Sends your event text to OpenAI when you click Evaluate. Requires OPENAI_API_KEY in the server environment."
        )
    st.code("\n".join(EXAMPLES), language="text")
    text = st.text_area("Operational event", EXAMPLES[0])
    if st.button("Evaluate event", type="primary"):
        if mode == "anthropic" and not (api_key or os.environ.get("ANTHROPIC_API_KEY")):
            st.error("Enter your Anthropic API key in the masked field above.")
        elif mode == "openai" and not os.environ.get("OPENAI_API_KEY"):
            st.error("OPENAI_API_KEY is not configured. Offline mode remains available.")
        else:
            try:
                with st.spinner("Validating the event and calling planning tools…"):
                    st.session_state["decision"] = (
                        spike,
                        text,
                        mode,
                        run(factory, text, mode, api_key=api_key),
                    )
            except Exception as exc:
                st.session_state.pop("decision", None)
                st.error(f"Event evaluation failed ({type(exc).__name__}); no decision was made.")
    saved = st.session_state.get("decision")
    if saved and not hasattr(saved[3], "risk_assessment"):
        st.session_state.pop("decision", None)
        saved = None
    if saved and saved[:3] == (spike, text, mode):
        decision = saved[3]
        st.markdown("### " + decision.action)
        st.write(decision.explanation.replace("$", "\\$"))
        if decision.risk_assessment:
            risk = decision.risk_assessment
            st.markdown("#### Compare runtime-aware policies")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Policy": p["policy"],
                            "Failure rate": f"{p['failure_rate']:.1%}",
                            "Risk upper bound": f"{p['failure_rate_95pct_interval'][1]:.1%}",
                            "Mean incremental profit ($)": round(p["mean_incremental_profit"], 2),
                            "Profit interval ($)": [
                                round(v, 2) for v in p["profit_mean_95pct_interval"]
                            ],
                            "Bounded runtime certificate": p["bounded_runtime_certificate"],
                            "Passes gates": p["qualifies"],
                        }
                        for p in risk["policies"]
                    ]
                ),
                hide_index=True,
            )
            st.caption(risk["assumptions"])
            st.caption(
                f"Buffered solve: {risk['buffered_solver_status']} · "
                f"Stochastic solve: {risk['stochastic_solver_status']} · "
                "Risk gate: upper failure bound ≤ 5%; economics gate: lower mean profit bound > $0."
            )
            selected = next(
                (p for p in risk["policies"] if p["policy"] == risk["selected_policy"]), None
            )
            if selected:
                st.plotly_chart(
                    timeline(
                        factory, selected["schedule"], "Recommended policy / " + selected["policy"]
                    ),
                    use_container_width=True,
                )
                st.success(
                    "Recommended within the synthetic runtime model. No external action is executed."
                )
        elif decision.candidate and decision.candidate.schedule is not None:
            st.plotly_chart(
                timeline(decision.factory, decision.candidate.schedule, "Event response candidate"),
                use_container_width=True,
            )
            with st.expander("Runtime uncertainty stress test"):
                stress = simulate(decision.factory, decision.candidate.schedule)
                st.json(stress)
        with st.expander("Structured event and tool trace"):
            st.json(jsonable(decision.event))
            st.json(jsonable(decision.trace))
        st.download_button(
            "Download event trace",
            json.dumps(jsonable(decision), indent=2),
            "gridshift-trace.json",
            "application/json",
        )
with evaluation:
    st.subheader("Scheduling and extraction benchmarks")
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
        extraction = report["event_extraction"]
        st.metric("Offline extraction", f"{extraction['passed']}/{extraction['total']}")
        with st.expander("Event extraction cases"):
            st.json(extraction["traces"])
        st.markdown("#### Scenario traces")
        split = st.radio("Seed split", ["development", "heldout"], horizontal=True)
        cases = [c for c in report["cases"] if c["split"] == split]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "seed": c["seed"],
                        "status": c["optimized"]["status"],
                        "baseline_cost": c["baseline_cost"],
                        "optimized_cost": c["optimized"]["cost"],
                        "lower_bound_dollars": c["optimized"]["lower_bound_dollars"],
                        "violations": len(c["validation_errors"]),
                    }
                    for c in cases
                ]
            ),
            hide_index=True,
        )
        selected_seed = st.selectbox("Inspect full scenario", [c["seed"] for c in cases])
        with st.expander("Inputs, schedules, bounds and failures"):
            st.json(next(c for c in cases if c["seed"] == selected_seed))
        st.download_button(
            "Download eval report",
            report_path.read_text(),
            "gridshift-evals.json",
            "application/json",
        )
    calibration_path = Path(__file__).parent / "evals/calibration.json"
    if calibration_path.exists():
        calibration = json.loads(calibration_path.read_text())
        st.markdown("#### Synthetic risk calibration · independent heldout outcomes")
        a, b, c = st.columns(3)
        a.metric("Heldout runtime trials", calibration["heldout_trials"])
        b.metric("Fitted Brier score", f"{calibration['brier_fitted']:.4f}")
        c.metric("Fixed-prior Brier score", f"{calibration['brier_fixed_prior']:.4f}")
        bins = calibration["reliability_bins"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration"))
        fig.add_trace(
            go.Scatter(
                x=[b["predicted"] for b in bins],
                y=[b["observed"] for b in bins],
                mode="markers+lines",
                name="Heldout synthetic observations",
            )
        )
        fig.update_layout(
            xaxis_title="Predicted failure probability",
            yaxis_title="Observed failure rate",
            template="plotly_dark",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(calibration["limitations"])
    st.info(
        "No API key needed. All displayed results are local synthetic evaluations. "
        "Optional live model adapters have mock tests; live language-model quality is unmeasured."
    )
with engineering:
    st.subheader("Model and assumptions")
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
Anthropic/OpenAI adapters are optional; offline eval scores do not measure LLM performance.
Stochastic planning shares placements across 24 training scenarios and is evaluated on 500 fresh draws.
Buffered reservations certify feasibility only for overruns of at most one hour.
Calibration uses disjoint synthetic runtime observations; real factory data is still needed.
""")
