"""
Fetch all open Kalshi markets and write a snapshot.

This is your original script with three changes, each marked `# FIX:` below:

  1. Liquidity is captured correctly. Kalshi exposes book liquidity as an
     integer number of cents in the ``liquidity`` field; the original code only
     read ``liquidity_dollars``, which the feed returns as 0. We now prefer the
     real dollar value, fall back to ``liquidity`` / 100, and leave it at 0 only
     when neither is present (the loader then fills a flagged estimate).
  2. Output is written to ``data/snapshots/`` (where the loader looks) as both
     CSV and Parquet. Parquet is the typed, compact format the store prefers.
  3. Numeric coercion only touches columns that actually exist, so a change in
     the API payload can't crash the run.

Run it, then load:
    python pipeline/fetch_kalshi.py
    python pipeline/load_snapshots.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

OUTPUT_FOLDER = config.SNAPSHOTS_DIR
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime(config.SNAPSHOT_TIME_FORMAT)
OUTPUT_CSV = OUTPUT_FOLDER / f"kalshi_markets_{timestamp}.csv"
OUTPUT_PARQUET = OUTPUT_FOLDER / f"kalshi_markets_{timestamp}.parquet"

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

print("Project Root :", ROOT)
print("Output File  :", OUTPUT_PARQUET)


# ============================================================================
# FETCH MARKETS
# ============================================================================
def fetch_all_markets():
    session = requests.Session()
    all_markets = []
    cursor = None

    while True:
        params = {"limit": 1000, "status": "open", "mve_filter": "exclude"}
        if cursor:
            params["cursor"] = cursor

        response = session.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        all_markets.extend(data["markets"])
        cursor = data.get("cursor")
        print(f"Fetched {len(all_markets):,} markets")

        if not cursor:
            break

    return all_markets


# ============================================================================
# BUILD DASHBOARD DATA
# ============================================================================
def build_dashboard_df(markets):
    df = pd.DataFrame(markets)

    numeric_columns = [
        "yes_bid_dollars", "yes_ask_dollars",
        "previous_yes_bid_dollars", "previous_yes_ask_dollars",
        "open_interest_fp", "volume_fp", "volume_24h_fp",
        "liquidity_dollars",
    ]
    # FIX 3: only coerce columns that exist in this payload.
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["series"] = df["event_ticker"].str.split("-").str[0]
    df["market"] = df["title"]
    df["outcome"] = df["yes_sub_title"].fillna(df.get("subtitle")).fillna("")

    df["bid"] = df["yes_bid_dollars"]
    df["ask"] = df["yes_ask_dollars"]
    df["spread"] = df["ask"] - df["bid"]
    df["change_24h"] = df["yes_bid_dollars"] - df["previous_yes_bid_dollars"]

    df["oi"] = df["open_interest_fp"]
    df["volume_24h"] = df["volume_24h_fp"]
    df["total_volume"] = df["volume_fp"]

    # FIX 1: real liquidity. Prefer the dollar field when populated, else convert
    # the cents field, else 0 (loader supplies a flagged estimate downstream).
    liquidity_dollars = pd.to_numeric(
        df.get("liquidity_dollars", 0), errors="coerce"
    ).fillna(0)
    if "liquidity" in df.columns:
        liquidity_cents = pd.to_numeric(df["liquidity"], errors="coerce").fillna(0)
        liquidity_dollars = liquidity_dollars.where(liquidity_dollars > 0, liquidity_cents / 100.0)
    df["liquidity_dollars"] = liquidity_dollars

    df["added"] = pd.to_datetime(df["created_time"], errors="coerce")
    df["expires"] = pd.to_datetime(df["close_time"], errors="coerce")

    dashboard_df = df[[
        "series", "market", "outcome", "change_24h", "bid", "ask", "spread",
        "oi", "volume_24h", "total_volume", "liquidity_dollars",
        "added", "expires", "ticker", "event_ticker",
    ]].copy()

    return dashboard_df.sort_values("oi", ascending=False).reset_index(drop=True)


# ============================================================================
# MAIN
# ============================================================================
def main():
    print("Downloading Kalshi markets...")
    markets = fetch_all_markets()

    print("Building dashboard dataframe...")
    df = build_dashboard_df(markets)

    print(f"Saving {len(df):,} rows...")
    df.to_csv(OUTPUT_CSV, index=False)
    # FIX 2: also write Parquet for the store.
    df.to_parquet(OUTPUT_PARQUET, index=False)

    real_liq = int((df["liquidity_dollars"] > 0).sum())
    print(f"\nSaved to:\n  {OUTPUT_CSV}\n  {OUTPUT_PARQUET}")
    print(f"Liquidity populated for {real_liq:,} / {len(df):,} markets.")
    if real_liq == 0:
        print("  (none from feed \u2014 the loader will fill flagged estimates)")

    print("\nTop 10 markets by OI:")
    print(df[["series", "market", "outcome", "oi", "volume_24h", "total_volume"]].head(10))


if __name__ == "__main__":
    main()
