"""About — what the numbers mean and where they come from."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parents[1]))

import config  # noqa: E402
import db      # noqa: E402
import theme   # noqa: E402
import ui      # noqa: E402

st.set_page_config(page_title=f"About · {config.APP_TITLE}", page_icon="\u25C8", layout="wide")
theme.inject_css()

if db.store_ready():
    ui.snapshot_sidebar()

ui.header("About", "How to read this dashboard", "Definitions, methodology and roadmap")

st.subheader("Source")
st.markdown(
    "Each snapshot is a single pull of all open markets from the Kalshi public "
    "API. Snapshots are loaded into a local DuckDB store, one row per market per "
    "pull. The dashboard currently shows the most recent snapshot."
)

st.subheader("Definitions")
st.markdown(
    "- **Open interest** — dollar value of contracts currently held open.\n"
    "- **24h volume** — dollars traded in the trailing 24 hours.\n"
    "- **Implied probability** — the mid-price between the yes bid and ask, read "
    "as the market's estimate of the event happening.\n"
    "- **Spread** — gap between yes bid and ask, in cents. Tighter spreads "
    "generally mean a more liquid, more confidently priced market.\n"
    "- **24h change** — move in the yes price over the last day, in cents."
)

st.subheader("Liquidity, and why some values are estimated")
st.markdown(
    "Kalshi can report a real liquidity figure — the dollar value of orders "
    "resting on a market's book. When a snapshot carries that figure, the "
    "dashboard uses it directly."
)
st.markdown(
    "When it's missing (as in the seed snapshot, whose feed didn't include it), "
    "we fall back to a transparent **estimate** so the column still ranks markets "
    "sensibly. The estimate combines the signals we do have:"
)
st.latex(
    r"\text{liquidity}_{\text{est}} = (1 - \text{spread}) \times "
    r"\big(%.2f \cdot \text{vol}_{24h} + %.2f \cdot \text{OI}\big)"
    % (config.LIQUIDITY_VOL_WEIGHT, config.LIQUIDITY_OI_WEIGHT)
)
st.markdown(
    "Tighter spreads and more recent traded notional / open interest all point to "
    "a more liquid market; the spread factor discounts markets whose wide quotes "
    "make their nominal size hard to trade against. Estimated values are flagged "
    "with an asterisk wherever they appear, and the weights live in `config.py`. "
    "It is a **ranking aid, not a quoted book depth** — treat it as relative, not exact."
)

st.subheader("Roadmap")
st.markdown(
    "- **Trends over time** — every snapshot is stored with its timestamp, so "
    "price / OI / liquidity history is already accumulating. Time-series views "
    "(per-market probability drift, liquidity build-up, momentum) switch on with "
    "no change to ingestion.\n"
    "- **Real liquidity everywhere** — once the fetch reliably captures Kalshi's "
    "liquidity field, estimates fall away automatically.\n"
    "- **More sources** — the same store can hold other venues for cross-market "
    "comparison."
)

if db.store_ready():
    t = db.snapshot_times()
    st.divider()
    st.caption(
        f"Store: {len(t)} snapshot(s) · latest {t[0]:%Y-%m-%d %H:%M UTC} · "
        f"{db.kpis(t[0])['n_markets']:,} markets"
    )
