"""
Explore — the analyst's workbench.

Two tabs:
  * Markets — full-text search, series / liquidity filters, a sortable formatted
    table and CSV export. Filters are tuned for the data's heavy skew (open
    interest spans single dollars to tens of millions), so the OI control uses
    preset thresholds rather than a useless linear slider.
  * Series breakdown — every series rolled up and ranked by total volume by
    default, with a chart of the leaders and a sortable, exportable table.
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))        # dashboard/ -> db, theme, ui, labels
sys.path.insert(0, str(_HERE.parents[1]))    # project root -> config

import config  # noqa: E402
import db      # noqa: E402
import labels  # noqa: E402
import theme   # noqa: E402
import ui      # noqa: E402

st.set_page_config(page_title=f"Explore · {config.APP_TITLE}", page_icon="\u25C8", layout="wide")
theme.inject_css()

if not db.store_ready():
    st.warning("No data loaded yet. Run `python pipeline/load_snapshots.py` first.")
    st.stop()

chosen = ui.snapshot_sidebar()
ui.header("Explore", "Market explorer", "Search and filter markets, or break the board down by series")

tab_markets, tab_series = st.tabs(["Markets", "Series breakdown"])

# ===========================================================================
# MARKETS
# ===========================================================================
with tab_markets:
    r1c1, r1c2 = st.columns([2, 3])
    text = r1c1.text_input("Search", placeholder="market, outcome or ticker\u2026").strip()
    series_sel = r1c2.multiselect("Series", options=db.series_options(chosen), placeholder="All series")

    r2c1, r2c2, r2c3, r2c4 = st.columns([2, 2, 2, 1])
    OI_PRESETS = {
        "Any": 0, "\u2265 $100": 100, "\u2265 $1K": 1_000,
        "\u2265 $10K": 10_000, "\u2265 $100K": 100_000, "\u2265 $1M": 1_000_000,
    }
    oi_label = r2c1.select_slider("Min. open interest", options=list(OI_PRESETS), value="Any")
    min_oi = OI_PRESETS[oi_label]
    max_spread_c = r2c2.slider("Max. spread (\u00a2)", min_value=1, max_value=100, value=100)

    SORT_FIELDS = {
        "Open interest": "oi", "24h volume": "volume_24h", "Total volume": "total_volume",
        "24h change": "change_24h", "Spread": "spread", "Liquidity": "liquidity_eff",
    }
    sort_label = r2c3.selectbox("Sort by", options=list(SORT_FIELDS), index=0)
    direction = r2c4.radio("Order", ["High\u2192low", "Low\u2192high"], index=0)

    df = db.search_markets(
        chosen, text=text, series=tuple(series_sel), min_oi=min_oi,
        max_spread=max_spread_c / 100.0, sort_by=SORT_FIELDS[sort_label],
        descending=(direction == "High\u2192low"),
    )

    capped = len(df) >= 2000
    st.caption(
        f"Showing {len(df):,}{'+ (capped at 2,000 \u2014 narrow your filters for more)' if capped else ''} "
        f"of {db.kpis(chosen)['n_markets']:,} markets"
    )

    if df.empty:
        st.info("No markets match these filters. Widen the search or lower the open-interest floor.")
    else:
        view = df.copy()
        view["implied"] = ((view["bid"] + view["ask"]) / 2).clip(0, 1)
        view["change_c"] = view["change_24h"] * 100
        view["spread_c"] = view["spread"] * 100
        display = view[[
            "series", "market", "outcome", "implied", "change_c", "spread_c",
            "oi", "volume_24h", "total_volume", "liquidity_eff", "expires", "ticker",
        ]]
        st.dataframe(
            display, width="stretch", hide_index=True, height=560,
            column_config={
                "series": st.column_config.TextColumn("Series", width="small"),
                "market": st.column_config.TextColumn("Market", width="large"),
                "outcome": st.column_config.TextColumn("Outcome", width="small"),
                "implied": st.column_config.ProgressColumn(
                    "Implied", help="Mid-price implied probability", format="percent",
                    min_value=0.0, max_value=1.0),
                "change_c": st.column_config.NumberColumn("24h \u0394\u00a2", format="%+d"),
                "spread_c": st.column_config.NumberColumn("Spread\u00a2", format="%d"),
                "oi": st.column_config.NumberColumn("Open int.", format="compact"),
                "volume_24h": st.column_config.NumberColumn("24h vol", format="compact"),
                "total_volume": st.column_config.NumberColumn("Total vol", format="compact"),
                "liquidity_eff": st.column_config.NumberColumn("Liquidity*", format="compact"),
                "expires": st.column_config.DatetimeColumn("Expires", format="MMM D, YYYY"),
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
            },
        )
        est_n = int(df["liquidity_is_estimated"].sum())
        note = "  ·  *liquidity estimated for all rows" if est_n == len(df) else (
            f"  ·  *liquidity estimated for {est_n:,} of {len(df):,} rows" if est_n else "")
        st.caption(f"Prices in cents · open interest / volume / liquidity in dollars{note}")
        st.download_button(
            "Download these rows (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"kalshi_explore_{chosen:%Y%m%d_%H%M%S}.csv",
            mime="text/csv", key="dl_markets",
        )

# ===========================================================================
# SERIES BREAKDOWN
# ===========================================================================
with tab_series:
    sb = db.series_breakdown(chosen).copy()
    sb["theme"] = sb["example"].map(lambda m: labels.event_label(m, 42))
    sb["avg_spread_c"] = sb["avg_spread"] * 100

    st.caption(
        f"{len(sb):,} series in this snapshot · "
        f"counts shown are markets and events (the feed has no per-trade tally)"
    )

    # --- Chart controls ---
    cc1, cc2 = st.columns([3, 2])
    METRICS = {
        "Total volume": ("total_volume", True),
        "24h volume": ("volume_24h", True),
        "Open interest": ("oi", True),
        "Liquidity": ("liquidity", True),
        "Markets": ("n_markets", False),
    }
    metric_label = cc1.selectbox("Rank series by", options=list(METRICS), index=0)
    metric_col, is_dollar = METRICS[metric_label]
    top_n = cc2.select_slider("Show top", options=[10, 15, 25, 50], value=15)

    ranked = sb.sort_values(metric_col, ascending=False).head(top_n)

    # --- Leaders chart ---
    ypos = list(range(len(ranked)))
    ticktext = [t if len(t) <= 42 else t[:41] + "\u2026" for t in ranked["theme"]]
    if is_dollar:
        bar_text = [theme.money(v) for v in ranked[metric_col]]
    else:
        bar_text = [f"{int(v):,}" for v in ranked[metric_col]]
    customdata = list(zip(
        ranked["series"], ranked["n_markets"], ranked["n_events"],
        [theme.money(v) for v in ranked["total_volume"]],
    ))
    fig = go.Figure(
        go.Bar(
            x=ranked[metric_col], y=ypos, orientation="h",
            marker_color=theme.ACCENT,
            text=bar_text, textposition="outside", cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "%{customdata[0]}<br>" + metric_label + " %{text}<br>"
                "%{customdata[1]} markets · %{customdata[2]} events<extra></extra>"
            ),
        )
    )
    fig.update_yaxes(tickmode="array", tickvals=ypos, ticktext=ticktext, autorange="reversed")
    fig.update_xaxes(range=theme.bar_range(ranked[metric_col]), title=None, showticklabels=False)
    theme.plotly_layout(fig, height=30 * len(ranked) + 50)
    st.subheader(f"Top series by {metric_label.lower()}")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # --- Detailed table (all series, sortable) ---
    st.subheader("All series")
    table = sb[[
        "series", "theme", "total_volume", "volume_24h", "oi", "liquidity",
        "n_markets", "n_events", "avg_spread_c", "n_moved",
    ]]
    st.dataframe(
        table, width="stretch", hide_index=True, height=480,
        column_config={
            "series": st.column_config.TextColumn("Series", width="small"),
            "theme": st.column_config.TextColumn("Theme / example", width="large"),
            "total_volume": st.column_config.NumberColumn("Total vol", format="compact"),
            "volume_24h": st.column_config.NumberColumn("24h vol", format="compact"),
            "oi": st.column_config.NumberColumn("Open int.", format="compact"),
            "liquidity": st.column_config.NumberColumn("Liquidity*", format="compact"),
            "n_markets": st.column_config.NumberColumn("Markets", format="%d"),
            "n_events": st.column_config.NumberColumn("Events", format="%d"),
            "avg_spread_c": st.column_config.NumberColumn("Avg spread\u00a2", format="%.1f"),
            "n_moved": st.column_config.NumberColumn("Moved 24h", format="%d"),
        },
    )
    all_est = bool(sb["liq_estimated"].all())
    st.caption(
        "Volume / open interest / liquidity in dollars · spread in cents"
        + ("  ·  *liquidity estimated" if all_est else "")
    )
    st.download_button(
        "Download series breakdown (CSV)",
        data=sb.drop(columns=["example"]).to_csv(index=False).encode("utf-8"),
        file_name=f"kalshi_series_{chosen:%Y%m%d_%H%M%S}.csv",
        mime="text/csv", key="dl_series",
    )
