# home.py
"""
Smart Shelf Analytics - Streamlit Dashboard
Reads reports.json (expects a list of historical reports) and visualizes
the latest report with hero metrics, action items, consumption analysis,
predictive insights and raw export options.

Place this file next to reports.json created by your pipeline.
Run: streamlit run home.py
"""

from __future__ import annotations
import streamlit as st
import json
import math
import io
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd
import altair as alt
import numpy as np
from pathlib import Path

# -------------------------
# Configuration / Helpers
# -------------------------
REPORTS_FILE = Path("reports/reports.json")


@st.cache_data
def load_reports(path: Path) -> List[Dict[str, Any]]:
    """Load reports.json and return list of reports (may be empty)."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            # if single object, wrap
            return [data]
    except Exception as e:
        st.error(f"Failed to read {path}: {e}")
        return []


def latest_report(reports: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not reports:
        return None
    # assume appended chronologically; else pick max generated_at
    try:
        return max(reports, key=lambda r: r.get("generated_at", 0))
    except Exception:
        return reports[-1]


def ts_to_str(ts: int) -> str:
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def calculate_shelf_status(report: Dict[str, Any]) -> str:
    """Return 'CRITICAL', 'WARNING', or 'HEALTHY' based on restock actions."""
    restock = report.get("restock_report", [])
    counts = {"RESTOCK_NOW": 0, "RESTOCK_SOON": 0}
    for it in restock:
        action = it.get("action", "").upper()
        if action == "RESTOCK_NOW":
            counts["RESTOCK_NOW"] += 1
        if action == "RESTOCK_SOON":
            counts["RESTOCK_SOON"] += 1
    if counts["RESTOCK_NOW"] > 0:
        return "CRITICAL"
    if counts["RESTOCK_SOON"] > 2:
        return "WARNING"
    return "HEALTHY"


# -------------------------
# UI Sections
# -------------------------

def render_header(report: Dict[str, Any]):
    # NOTE: set_page_config must be called before any other Streamlit calls.
    # This function now only renders header content (no set_page_config).
    st.markdown(
        """
    <style>
      .hero { border-radius: 12px; padding: 18px; color: white; }
      .small-muted { color: #666; font-size: 0.9rem; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("📊 Smart Shelf Analytics Dashboard")
    st.write("A concise view of shelf health, actions and forecasts. Data shown below is from the latest analysis run.")


def render_hero_section(report: Dict[str, Any]):
    # traffic light
    status = calculate_shelf_status(report)
    if status == "CRITICAL":
        bg = "#FF4444"
        emoji = "🔴"
        message = "IMMEDIATE ACTION REQUIRED"
        desc = "Shelf running low on critical items"
    elif status == "WARNING":
        bg = "#FFA500"
        emoji = "🟠"
        message = "RESTOCK SOON"
        desc = "Activity detected — monitor closely"
    else:
        bg = "#44DD44"
        emoji = "🟢"
        message = "HEALTHY INVENTORY"
        desc = "All items in optimal range"

    cols = st.columns([2, 3, 3])
    with cols[0]:
        st.markdown(
            f"""
        <div class="hero" style="background:{bg}">
          <div style="text-align:center;">
            <h1 style="margin:0;font-size:48px">{emoji}</h1>
            <h2 style="margin:6px 0 0 0;font-size:22px">{message}</h2>
            <div class="small-muted" style="margin-top:6px">{desc}</div>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Next restock countdown
    restock = report.get("restock_report", [])
    default_hours = 999.0
    next_hours = default_hours
    if restock:
        # pick the smallest median p50 across items
        try:
            p50s = [float(it.get("p50", default_hours)) for it in restock]
            next_hours = min(p50s) if p50s else default_hours
        except Exception:
            next_hours = default_hours

    with cols[1]:
        icon = "✅" if next_hours > 6 else "⏱️" if next_hours > 2 else "⏰"
        urgency_pct = int((1 - min(next_hours / 24.0, 1.0)) * 100)
        st.metric("⏱️ TIME UNTIL NEXT RESTOCK NEEDED", f"{next_hours:.1f} hours", delta=f"{urgency_pct}% urgent")

    # three side-by-side summary cards
    with cols[2]:
        demand = report.get("demand_forecast", {}).get("forecasts", {})
        total_consumption = sum(demand.values()) if isinstance(demand, dict) else 0.0
        st.metric("📦 Total Items Removed (g)", f"{total_consumption:.0f}g")

        data_quality = 0.0
        try:
            data_quality = (report.get("kalman_sparse_count", 0) / max(1, report.get("n_samples", 1))) * 100.0
        except Exception:
            data_quality = 0.0
        st.metric("✅ Data Quality", f"{data_quality:.0f}%")

        n_items = len(report.get("restock_report", []))
        st.metric("📊 Items Tracked", n_items)


def render_action_section(report: Dict[str, Any]):
    st.subheader("🎯 Immediate Action Items")
    restock = report.get("restock_report", [])
    critical = [r for r in restock if r.get("action") == "RESTOCK_NOW"]
    soon = [r for r in restock if r.get("action") == "RESTOCK_SOON"]

    if critical:
        st.error("⚠️ CRITICAL: The following need restocking TODAY")
        for it in critical:
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"### 🛒 {it.get('item_id')}")
                    st.write(f"**Risk score:** {it.get('risk'):.3f}")
                with c2:
                    st.metric("⏱️ Hours Left (median)", f"{it.get('p50', 0):.1f}h", delta=f"{it.get('p5',0):.0f}-{it.get('p95',0):.0f}h")
                with c3:
                    risk_perc = min(100, float(it.get("risk", 0.0) * 100))
                    st.progress(risk_perc / 100.0)
                    st.caption(f"Risk: {risk_perc:.0f}%")
    else:
        st.success("✅ No items need immediate restocking.")

    if soon:
        st.markdown("---")
        st.subheader("👀 Watch These Soon")
        df = pd.DataFrame([{
            "Item": it.get("item_id"),
            "Restock In (h)": float(it.get("p50", 0)),
            "Median (h)": float(it.get("p50", 0)),
            "Current Level (g)": it.get("current_inventory", "n/a"),
            "Status": it.get("action")
        } for it in soon])
        st.dataframe(df, use_container_width=True)
    st.divider()


def render_consumption_analysis(report: Dict[str, Any]):
    st.subheader("📈 Consumption Analysis")

    # Pie chart: demand forecast breakdown
    forecasts = report.get("demand_forecast", {}).get("forecasts", {})
    if isinstance(forecasts, dict) and forecasts:
        pie_df = pd.DataFrame(
            [{"type": k, "value": float(v)} for k, v in forecasts.items() if float(v) > 0.0]
        )
        if pie_df.empty:
            st.info("No forecasted demand split available.")
        else:
            pie = alt.Chart(pie_df).mark_arc().encode(
                theta=alt.Theta(field="value", type="quantitative"),
                color=alt.Color(field="type", type="nominal"),
                tooltip=["type", "value"]
            )
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Types of Removals (Breakdown)")
                st.altair_chart(pie, use_container_width=True)
            # simple "timeline" synthesized from n_samples (as we don't have raw per-event times)
            with col2:
                st.markdown("### Consumption Timeline (synthetic)")
                n = int(report.get("n_samples", 0))
                if n <= 1:
                    st.info("Not enough sample data to build a timeline.")
                else:
                    # Create a synthetic cumulative series to show trend shape
                    x = np.arange(n)
                    # Use cumulative of (some proxy) — here we split total demand evenly, if available
                    total = sum([float(v) for v in forecasts.values()]) if forecasts else 0.0
                    if total <= 0.0:
                        # fallback: synthetic random walk but deterministic
                        values = np.cumsum(np.sin(x / max(1, n/10)) + 1.0)
                        values = (values / values.max()) * 100.0
                        df = pd.DataFrame({"index": x, "value": values})
                    else:
                        # evenly distribute total across n points
                        values = np.cumsum(np.ones(n) * (total / n))
                        df = pd.DataFrame({"index": x, "value": values})
                    line = alt.Chart(df).mark_line(point=False).encode(
                        x=alt.X("index:Q", title="Sample index"),
                        y=alt.Y("value:Q", title="Cumulative (g)"),
                        tooltip=["index", "value"]
                    )
                    st.altair_chart(line.interactive(), use_container_width=True)

    else:
        st.info("No demand forecasts available in this report.")

    # Hourly breakdown if present (try to pull hourly summary)
    hourly = None
    try:
        hourly = report.get("hourly_summary", None)
    except Exception:
        hourly = None

    if hourly:
        h_df = pd.DataFrame([{"hour": k, "consumption": v.get("total_consumed", 0)} for k, v in hourly.items()])
        st.markdown("### Hourly Consumption Breakdown")
        bar = alt.Chart(h_df).mark_bar().encode(x="hour:O", y="consumption:Q", tooltip=["hour", "consumption"])
        st.altair_chart(bar, use_container_width=True)
    st.divider()


def render_predictive_insights(report: Dict[str, Any]):
    st.subheader("🔮 Predictive Insights")

    restock = report.get("restock_report", [])
    if not restock:
        st.info("No restock forecasts available.")
        return

    # Build a small timeline Gantt-like chart from p5/p95/p50 values
    try:
        rows = []
        for it in restock:
            rows.append({
                "item": it.get("item_id"),
                "p5": float(it.get("p5", 0.0)),
                "p50": float(it.get("p50", 0.0)),
                "p95": float(it.get("p95", 0.0)),
                "action": it.get("action", "MONITOR")
            })
        df = pd.DataFrame(rows).sort_values("p50")
        base = alt.Chart(df).mark_bar(size=8).encode(
            x=alt.X("p5:Q", title="Hours from now"),
            x2="p95:Q",
            y=alt.Y("item:N", sort='-x'),
            color=alt.Color("action:N",
                            scale=alt.Scale(domain=["RESTOCK_NOW", "RESTOCK_SOON", "MONITOR"],
                                            range=["#FF4444", "#FFA500", "#44DD44"])),
            tooltip=["item", "p5", "p50", "p95", "action"]
        )
        median_line = alt.Chart(df).mark_tick(color="black", thickness=2, size=18).encode(
            x="p50:Q",
            y=alt.Y("item:N", sort='-x'),
            tooltip=["item", "p50"]
        )
        st.altair_chart(base + median_line, use_container_width=True)
    except Exception as e:
        st.error(f"Unable to render forecast timeline: {e}")

    st.divider()


def render_anomalies_and_health(report: Dict[str, Any]):
    st.subheader("🚨 Anomalies & System Health")

    # Anomalies: try to detect from kalman sparse deltas if any stored (we stored none in simple example)
    anomalies = []
    try:
        # If the report included anomalies list (future extension), use it
        anomalies = report.get("anomalies", [])
    except Exception:
        anomalies = []

    if not anomalies:
        st.success("✅ No anomalies recorded in the latest run (or none were flagged).")
    else:
        for a in anomalies:
            st.warning(f"{a.get('title')}: {a.get('description')} (Severity: {a.get('severity')})")

    # System health / calibration
    data_quality = (report.get("kalman_sparse_count", 0) / max(1, report.get("n_samples", 1))) * 100.0
    st.metric("Data Integrity", f"{data_quality:.1f}%")
    # Position accuracy placeholder
    pos_acc = report.get("position_accuracy", None)
    if pos_acc is None:
        pos_acc = 90.0  # default placeholder
    st.metric("Position Detection Accuracy", f"{pos_acc:.1f}%")
    st.divider()


def render_debug_and_exports(report: Dict[str, Any]):
    st.subheader("🔬 Raw Data & Exports")

    with st.expander("📋 View Full Report JSON", expanded=False):
        st.json(report)
        buf = io.StringIO()
        json.dump(report, buf, indent=2)
        buf.seek(0)
        st.download_button("📥 Download Report (JSON)", data=buf.getvalue(), file_name=f"report_{report.get('generated_at', 'latest')}.json", mime="application/json")

    with st.expander("📊 Export Restock Forecasts (CSV)", expanded=False):
        rr = report.get("restock_report", [])
        if rr:
            df = pd.DataFrame(rr)
            csv = df.to_csv(index=False)
            st.download_button("📥 Download Restock CSV", data=csv, file_name=f"restock_{report.get('generated_at', 'latest')}.csv", mime="text/csv")
            st.dataframe(df.head(50), use_container_width=True)
        else:
            st.info("No restock forecasts available to export.")

    st.markdown("---")
    st.caption(f"Report generated at: {ts_to_str(report.get('generated_at', 0))}  •  Samples: {report.get('n_samples', 0)}  •  Events indexed: {report.get('events_indexed', 0)}")


# -------------------------
# Main
# -------------------------
def main():
    # MUST call set_page_config BEFORE any other Streamlit API calls or cached functions.
    # st.set_page_config(
    #     page_title="Smart Shelf Analytics",
    #     page_icon="📊",
    #     layout="wide",
    #     initial_sidebar_state="expanded",
    # )

    # Now safe to load cached functions and render header
    reports = load_reports(REPORTS_FILE)
    report = latest_report(reports)

    render_header(report if report else {})
    if not report:
        st.error("No reports found. Run the analysis pipeline first (it creates reports.json).")
        return

    # Hero metrics
    render_hero_section(report)

    # Actions
    render_action_section(report)

    # Consumption
    render_consumption_analysis(report)

    # Predictive insights
    render_predictive_insights(report)

    # Anomalies & Health
    render_anomalies_and_health(report)

    # Debug & exports
    render_debug_and_exports(report)

    st.markdown(
        """
    <div style="text-align:center;color:#888;margin-top:20px">
      Smart Shelf Analytics v1.0 · Built with ❤️
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
