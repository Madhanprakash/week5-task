"""Helpdesk dashboard: KPI cards, Plotly charts and the recent complaints table."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db

NAVY, TEAL, SLATE = "#22d3ee", "#34d399", "#8b9ab5"  # NAVY now = cyan accent
PRIORITY_COLORS = {"Low": "#64748b", "Medium": "#22d3ee", "High": "#f59e0b", "Critical": "#f87171"}
CATEGORY_COLORS = ["#22d3ee", "#34d399", "#f59e0b", "#818cf8", "#f472b6", "#fb923c", "#94a3b8"]
OPEN_STATES = {"Open", "Assigned", "In Progress", "Pending Customer Response", "Reopened"}


KPI_ICONS = {"Total Complaints": "🗂️", "Open": "📬", "In Progress": "⚙️", "Resolved": "✅", "Critical": "🚨"}


def kpi_card(label: str, value: int, hint: str, accent: str) -> str:
    return (f'<div class="kpi" style="--accent:{accent}"><div class="kpi-icon">{KPI_ICONS.get(label, "")}</div>'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-hint">{hint}</div></div>')


def _style(fig, title: str):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#ffffff"), x=0.01),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#b6c2d9"),
        margin=dict(l=8, r=8, t=48, b=8), height=330,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def render_dashboard() -> None:
    df = db.all_complaints()
    st.markdown('<div class="page-title">📊 <span class="grad">Dashboard</span></div>'
                '<div class="muted">Live overview of customer complaints.</div>',
                unsafe_allow_html=True)
    if df.empty:
        st.info("No complaints yet. They will appear here as customers submit them.")
        return

    total = len(df)
    open_n = int(df["status"].isin(["Open", "Assigned", "Reopened"]).sum())
    in_prog = int((df["status"] == "In Progress").sum())
    resolved = int(df["status"].isin(["Resolved", "Closed"]).sum())
    critical = int(((df["priority"] == "Critical") & df["status"].isin(OPEN_STATES)).sum())

    cards = [("Total Complaints", total, "All time", NAVY),
             ("Open", open_n, "Open, assigned or reopened", "#22d3ee"),
             ("In Progress", in_prog, "Being worked on", "#f59e0b"),
             ("Resolved", resolved, "Resolved or closed", TEAL),
             ("Critical", critical, "Active critical cases", "#f87171")]
    for col, args in zip(st.columns(5), cards):
        col.markdown(kpi_card(*args), unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        with st.container(border=True):
            d = df.assign(date=pd.to_datetime(df["created_at"]).dt.date)
            daily = d.groupby("date").size().rename("Complaints").reset_index()
            full = pd.date_range(daily["date"].min(), pd.Timestamp.today().date())
            daily = (daily.set_index(pd.to_datetime(daily["date"]))["Complaints"]
                     .reindex(full, fill_value=0).rename_axis("Date").reset_index())
            daily["7-day average"] = daily["Complaints"].rolling(7, min_periods=1).mean().round(2)
            fig = px.area(daily, x="Date", y="Complaints", color_discrete_sequence=[TEAL])
            fig.add_scatter(x=daily["Date"], y=daily["7-day average"], mode="lines",
                            name="7-day average", line=dict(color="#f59e0b", width=2))
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="rgba(148,163,184,.15)")
            st.plotly_chart(_style(fig, "Complaint trend"), width="stretch")
    with right:
        with st.container(border=True):
            cat = df["category"].value_counts().rename_axis("Category").reset_index(name="Count")
            fig = px.pie(cat, names="Category", values="Count", hole=0.58,
                         color_discrete_sequence=CATEGORY_COLORS)
            fig.update_traces(textinfo="percent", sort=False)
            st.plotly_chart(_style(fig, "Complaints by category"), width="stretch")

    b1, b2 = st.columns([2, 3])
    with b1:
        with st.container(border=True):
            pr = (df["priority"].value_counts().reindex(db.PRIORITIES, fill_value=0)
                  .rename_axis("Priority").reset_index(name="Count"))
            fig = px.bar(pr, x="Priority", y="Count", color="Priority", text="Count",
                         color_discrete_map=PRIORITY_COLORS)
            fig.update_layout(showlegend=False)
            fig.update_yaxes(gridcolor="rgba(148,163,184,.15)")
            st.plotly_chart(_style(fig, "Complaints by priority"), width="stretch")
    with b2:
        with st.container(border=True):
            st.markdown('<div class="chart-title">Recent complaints</div>', unsafe_allow_html=True)
            recent = df.head(8)[["complaint_id", "customer_name", "category", "priority",
                                 "status", "created_at"]]
            recent.columns = ["ID", "Customer", "Category", "Priority", "Status", "Submitted"]
            st.dataframe(recent, hide_index=True, width="stretch", height=290)
            if st.button("View all complaints →", key="dash_to_list"):
                st.session_state["hd_page"] = "Complaints"
                st.rerun()
