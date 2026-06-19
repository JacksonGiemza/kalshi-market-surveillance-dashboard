"""
Overview — the headline page.

Reads top-to-bottom like a briefing: where the money sits (open interest), how
it concentrates across series, and what moved in the last 24h. Built for the
view-only audience; the Explore page is where analysts dig in.

Run from the project root:
    streamlit run dashboard/Overview.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))            # dashboard/  -> db, theme
sys.path.insert(0, str(_HERE.parent))     # project root -> config

import config  # noqa: E402
import db      # noqa: E402
import labels  # noqa: E402
import theme   # noqa: E402
import ui      # noqa: E402

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon="\u25C8",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.inject_css()


# ---------------------------------------------------------------------------
# Empty state — direction, not an apology
# ---------------------------------------------------------------------------
if not db.store_ready():
    st.markdown('<div class="eyebrow">No data yet</div>', unsafe_allow_html=True)
    st.title("Load a snapshot to begin")
    st.write(
        "Drop a `kalshi_markets_*.csv` (or `.parquet`) into "
        "`data/snapshots/`, then build the store:"
    )
    st.code("python pipeline/load_snapshots.py", language="bash")
    st.stop()


# ---------------------------------------------------------------------------
# Snapshot selector  (one option today; the hook for time-series tomorrow)
# ---------------------------------------------------------------------------
chosen = ui.snapshot_sidebar()
k = db.kpis(chosen)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
ui.header(
    f"Snapshot · {chosen:%b %d, %Y · %H:%M UTC}",
    config.APP_TITLE,
    config.APP_TAGLINE,
)

if k["all_liq_estimated"]:
    st.info(
        "Liquidity in this snapshot is **estimated** from spread, volume and open "
        "interest — the raw feed didn't include book depth. See **About** for the "
        "method. Once a snapshot carries real liquidity, that value is used instead.",
        icon="\u2139\uFE0F",
    )

st.write("")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total open interest", theme.money(k["total_oi"]))
c2.metric("24h volume", theme.money(k["total_vol_24h"]))
c3.metric("Active markets", f"{k['n_markets']:,}")
c4.metric("Series", f"{k['n_series']:,}")
c5.metric("Events", f"{k['n_events']:,}")

st.caption(
    f"{k['n_moved']:,} markets moved in the last 24h · biggest gain "
    f"**{labels.clean_market_label(k['top_mover_market'], k['top_mover_outcome'], 48)}** "
    f"{theme.change_cents(k['top_mover_change'])}"
)

st.divider()

# ---------------------------------------------------------------------------
# Where the money sits
# ---------------------------------------------------------------------------
left, right = st.columns(2, gap="large")

with left:
    st.subheader("Largest markets by open interest")
    top = db.top_markets_by_oi(chosen, config.DEFAULT_TOP_N)
    ypos = list(range(len(top)))
    ticktext = [labels.clean_market_label(m, o, 44)
                for m, o in zip(top["market"], top["outcome"])]
    fulltext = [f"{m} · {o}" for m, o in zip(top["market"], top["outcome"])]
    fig = go.Figure(
        go.Bar(
            x=top["oi"],
            y=ypos,
            orientation="h",
            marker_color=theme.ACCENT,
            text=[theme.money(v) for v in top["oi"]],
            textposition="outside",
            cliponaxis=False,
            customdata=fulltext,
            hovertemplate="%{customdata}<br>OI %{text}<extra></extra>",
        )
    )
    fig.update_yaxes(tickmode="array", tickvals=ypos, ticktext=ticktext,
                     autorange="reversed")
    fig.update_xaxes(range=theme.bar_range(top["oi"]), title=None, showticklabels=False)
    theme.plotly_layout(fig, height=30 * len(top) + 40)
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

with right:
    st.subheader("Concentration by series")
    series = db.oi_by_series(chosen, config.DEFAULT_TOP_N)
    ypos = list(range(len(series)))
    ticktext = [labels.event_label(ex, 34) for ex in series["example"]]
    fig = go.Figure(
        go.Bar(
            x=series["oi"],
            y=ypos,
            orientation="h",
            marker_color=theme.INK,
            text=[theme.money(v) for v in series["oi"]],
            textposition="outside",
            cliponaxis=False,
            customdata=series[["series", "n_markets"]],
            hovertemplate="%{customdata[0]} · OI %{text}<br>"
                          "%{customdata[1]} markets<extra></extra>",
        )
    )
    fig.update_yaxes(tickmode="array", tickvals=ypos, ticktext=ticktext,
                     autorange="reversed")
    fig.update_xaxes(range=theme.bar_range(series["oi"]), title=None, showticklabels=False)
    theme.plotly_layout(fig, height=30 * len(series) + 40)
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

st.divider()

# ---------------------------------------------------------------------------
# What moved
# ---------------------------------------------------------------------------
st.subheader("Biggest 24h moves")
st.caption("Markets with open interest, ranked by change in the yes price.")
gainers, losers = db.top_movers(chosen, 10)
gcol, lcol = st.columns(2, gap="large")


def mover_chart(frame, color):
    ypos = list(range(len(frame)))
    ticktext = [labels.clean_market_label(m, o, 40)
                for m, o in zip(frame["market"], frame["outcome"])]
    fulltext = [f"{m} · {o}" for m, o in zip(frame["market"], frame["outcome"])]
    fig = go.Figure(
        go.Bar(
            x=(frame["change_24h"] * 100),
            y=ypos,
            orientation="h",
            marker_color=color,
            text=[theme.change_cents(v) for v in frame["change_24h"]],
            textposition="outside",
            cliponaxis=False,
            customdata=fulltext,
            hovertemplate="%{customdata}<br>%{text}<extra></extra>",
        )
    )
    fig.update_yaxes(tickmode="array", tickvals=ypos, ticktext=ticktext,
                     autorange="reversed")
    fig.update_xaxes(range=theme.bar_range(frame["change_24h"] * 100),
                     title="change (\u00a2)", zeroline=True)
    theme.plotly_layout(fig, height=30 * len(frame) + 50)
    return fig


with gcol:
    st.markdown("**Gainers**")
    if len(gainers):
        st.plotly_chart(mover_chart(gainers, theme.UP),
                        width='stretch', config={"displayModeBar": False})
    else:
        st.caption("No upward moves in this snapshot.")

with lcol:
    st.markdown("**Decliners**")
    if len(losers):
        st.plotly_chart(mover_chart(losers, theme.DOWN),
                        width='stretch', config={"displayModeBar": False})
    else:
        st.caption("No downward moves in this snapshot.")
