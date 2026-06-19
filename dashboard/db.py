"""
Query layer for the dashboard.

Every read the UI needs is a named function here, so pages never write SQL
inline and the "marts" stay in one place. Each query is parameterised by
``snapshot_time`` — today the app passes the latest, but the same functions will
serve historical/time-series views unchanged when those get switched on.

Results are cached by Streamlit so repeated interactions (filtering, re-sorting)
don't re-hit the database.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


# ---------------------------------------------------------------------------
# Connection / availability
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Open a read-only connection to the store (shared across reruns)."""
    return duckdb.connect(str(config.DB_PATH), read_only=True)


def store_ready() -> bool:
    """True when the store exists and holds at least one row."""
    if not config.DB_PATH.exists():
        return False
    try:
        con = get_connection()
        n = con.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
        return n > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Snapshot selection
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def snapshot_times() -> list[datetime]:
    con = get_connection()
    rows = con.execute(
        "SELECT DISTINCT snapshot_time FROM market_snapshots ORDER BY snapshot_time DESC"
    ).fetchall()
    return [r[0] for r in rows]


def latest_snapshot_time() -> datetime:
    return snapshot_times()[0]


# ---------------------------------------------------------------------------
# Headline marts
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def kpis(snapshot_time: datetime) -> dict:
    con = get_connection()
    row = con.execute(
        """
        SELECT
            SUM(oi)                       AS total_oi,
            SUM(volume_24h)               AS total_vol_24h,
            COUNT(*)                      AS n_markets,
            COUNT(DISTINCT series)        AS n_series,
            COUNT(DISTINCT event_ticker)  AS n_events,
            SUM(CASE WHEN change_24h <> 0 THEN 1 ELSE 0 END) AS n_moved,
            BOOL_AND(liquidity_is_estimated) AS all_liq_estimated
        FROM market_snapshots
        WHERE snapshot_time = ?
        """,
        [snapshot_time],
    ).fetchone()

    top = con.execute(
        """
        SELECT market, outcome, change_24h
        FROM market_snapshots
        WHERE snapshot_time = ?
        ORDER BY change_24h DESC
        LIMIT 1
        """,
        [snapshot_time],
    ).fetchone()

    return {
        "total_oi": row[0] or 0.0,
        "total_vol_24h": row[1] or 0.0,
        "n_markets": row[2] or 0,
        "n_series": row[3] or 0,
        "n_events": row[4] or 0,
        "n_moved": row[5] or 0,
        "all_liq_estimated": bool(row[6]),
        "top_mover_market": top[0] if top else "—",
        "top_mover_outcome": top[1] if top else "",
        "top_mover_change": top[2] if top else 0.0,
    }


@st.cache_data(show_spinner=False)
def top_markets_by_oi(snapshot_time: datetime, n: int) -> pd.DataFrame:
    con = get_connection()
    return con.execute(
        """
        SELECT market, outcome, oi, volume_24h, bid, ask, spread,
               liquidity_eff, liquidity_is_estimated
        FROM market_snapshots
        WHERE snapshot_time = ?
        ORDER BY oi DESC
        LIMIT ?
        """,
        [snapshot_time, n],
    ).df()


@st.cache_data(show_spinner=False)
def top_movers(snapshot_time: datetime, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (gainers, losers) — the n largest up and down 24h moves."""
    con = get_connection()
    # Only markets with real liquidity to move (some OI) and a non-zero change,
    # so the lists aren't dominated by thin markets ticking a single cent.
    base = """
        SELECT market, outcome, change_24h, bid, ask, oi
        FROM market_snapshots
        WHERE snapshot_time = ? AND change_24h {op} 0 AND oi > 0
        ORDER BY change_24h {dir}
        LIMIT ?
    """
    gainers = con.execute(
        base.format(op=">", dir="DESC"), [snapshot_time, n]
    ).df()
    losers = con.execute(
        base.format(op="<", dir="ASC"), [snapshot_time, n]
    ).df()
    return gainers, losers


@st.cache_data(show_spinner=False)
def oi_by_series(snapshot_time: datetime, n: int) -> pd.DataFrame:
    con = get_connection()
    return con.execute(
        """
        SELECT series,
               SUM(oi)            AS oi,
               SUM(volume_24h)    AS volume_24h,
               COUNT(*)           AS n_markets,
               arg_max(market, oi) AS example
        FROM market_snapshots
        WHERE snapshot_time = ?
        GROUP BY series
        ORDER BY oi DESC
        LIMIT ?
        """,
        [snapshot_time, n],
    ).df()


# ---------------------------------------------------------------------------
# Explore page
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def series_breakdown(snapshot_time: datetime) -> pd.DataFrame:
    """Per-series rollup for the Explore breakdown, ranked by total volume.

    ``example`` is the highest-OI market in the series, used to derive a
    human-readable theme. ``n_markets`` / ``n_events`` are the closest the feed
    gets to a 'number of trades' count — Kalshi's snapshot carries dollar volume
    and open interest, not a trade tally.
    """
    con = get_connection()
    return con.execute(
        """
        SELECT series,
               arg_max(market, oi)              AS example,
               SUM(total_volume)                AS total_volume,
               SUM(volume_24h)                  AS volume_24h,
               SUM(oi)                          AS oi,
               SUM(liquidity_eff)               AS liquidity,
               COUNT(*)                         AS n_markets,
               COUNT(DISTINCT event_ticker)     AS n_events,
               AVG(spread)                      AS avg_spread,
               SUM(CASE WHEN change_24h <> 0 THEN 1 ELSE 0 END) AS n_moved,
               BOOL_AND(liquidity_is_estimated) AS liq_estimated
        FROM market_snapshots
        WHERE snapshot_time = ?
        GROUP BY series
        ORDER BY total_volume DESC
        """,
        [snapshot_time],
    ).df()


@st.cache_data(show_spinner=False)
def series_options(snapshot_time: datetime) -> list[str]:
    con = get_connection()
    rows = con.execute(
        """
        SELECT series FROM market_snapshots
        WHERE snapshot_time = ?
        GROUP BY series ORDER BY SUM(oi) DESC
        """,
        [snapshot_time],
    ).fetchall()
    return [r[0] for r in rows if r[0]]


@st.cache_data(show_spinner=False)
def search_markets(
    snapshot_time: datetime,
    text: str = "",
    series: tuple[str, ...] = (),
    min_oi: float = 0.0,
    max_spread: float = 1.0,
    sort_by: str = "oi",
    descending: bool = True,
) -> pd.DataFrame:
    con = get_connection()
    clauses = ["snapshot_time = ?", "oi >= ?", "spread <= ?"]
    params: list = [snapshot_time, min_oi, max_spread]

    if text:
        clauses.append("(market ILIKE ? OR outcome ILIKE ? OR ticker ILIKE ?)")
        like = f"%{text}%"
        params += [like, like, like]

    if series:
        placeholders = ",".join("?" for _ in series)
        clauses.append(f"series IN ({placeholders})")
        params += list(series)

    allowed_sort = {
        "oi", "volume_24h", "total_volume", "change_24h",
        "spread", "liquidity_eff", "bid", "ask",
    }
    sort_col = sort_by if sort_by in allowed_sort else "oi"
    direction = "DESC" if descending else "ASC"

    sql = f"""
        SELECT series, market, outcome, bid, ask, spread, change_24h,
               oi, volume_24h, total_volume, liquidity_eff,
               liquidity_is_estimated, expires, ticker, event_ticker
        FROM market_snapshots
        WHERE {' AND '.join(clauses)}
        ORDER BY {sort_col} {direction}
        LIMIT 2000
    """
    return con.execute(sql, params).df()
