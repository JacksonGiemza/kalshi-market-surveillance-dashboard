"""
Ingest snapshot files into the DuckDB store.

Run this after every fetch (or on a schedule). It is incremental and
idempotent: each snapshot file is loaded exactly once, tracked by name in a
``loaded_files`` table, so re-running never duplicates rows.

    python pipeline/load_snapshots.py

The dashboard reads from the resulting ``market_snapshots`` table. Today the app
only queries the most recent snapshot, but because every snapshot is appended
with its own ``snapshot_time``, the full history accumulates automatically and
time-series views can be switched on later with no change to ingestion.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config          # noqa: E402
import liquidity        # noqa: E402

# Column order written into market_snapshots (snapshot_time is prepended).
SOURCE_COLUMNS = [
    "series", "market", "outcome", "change_24h", "bid", "ask", "spread",
    "oi", "volume_24h", "total_volume", "liquidity_dollars",
    "added", "expires", "ticker", "event_ticker",
]
DERIVED_COLUMNS = ["liquidity_est", "liquidity_eff", "liquidity_is_estimated"]
NUMERIC_COLUMNS = [
    "change_24h", "bid", "ask", "spread", "oi", "volume_24h",
    "total_volume", "liquidity_dollars",
]

CREATE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_time         TIMESTAMP,
    series                VARCHAR,
    market                VARCHAR,
    outcome               VARCHAR,
    change_24h            DOUBLE,
    bid                   DOUBLE,
    ask                   DOUBLE,
    spread                DOUBLE,
    oi                    DOUBLE,
    volume_24h            DOUBLE,
    total_volume          DOUBLE,
    liquidity_dollars     DOUBLE,
    liquidity_est         DOUBLE,
    liquidity_eff         DOUBLE,
    liquidity_is_estimated BOOLEAN,
    added                 TIMESTAMP,
    expires               TIMESTAMP,
    ticker                VARCHAR,
    event_ticker          VARCHAR
);
"""

CREATE_LOADED_FILES = """
CREATE TABLE IF NOT EXISTS loaded_files (
    filename      VARCHAR PRIMARY KEY,
    snapshot_time TIMESTAMP,
    rows          BIGINT,
    loaded_at     TIMESTAMP
);
"""


def parse_snapshot_time(filename: str) -> datetime | None:
    match = re.search(config.SNAPSHOT_FILENAME_RE, filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), config.SNAPSHOT_TIME_FORMAT)
    except ValueError:
        return None


def discover_snapshot_files() -> list[Path]:
    files: list[Path] = []
    for pattern in config.SNAPSHOT_GLOBS:
        files.extend(config.SNAPSHOTS_DIR.glob(pattern))
    return sorted(set(files))


def read_snapshot(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def prepare_frame(df: pd.DataFrame, snapshot_time: datetime) -> pd.DataFrame:
    # Guarantee every expected source column exists.
    for col in SOURCE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = liquidity.add_liquidity_columns(df)

    for col in ("added", "expires"):
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)

    df["snapshot_time"] = snapshot_time

    ordered = ["snapshot_time"] + SOURCE_COLUMNS[:11] + DERIVED_COLUMNS + SOURCE_COLUMNS[11:]
    return df[ordered]


def main() -> None:
    config.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH))
    con.execute(CREATE_SNAPSHOTS)
    con.execute(CREATE_LOADED_FILES)

    already = set(
        row[0] for row in con.execute("SELECT filename FROM loaded_files").fetchall()
    )

    files = discover_snapshot_files()
    print(f"Found {len(files)} snapshot file(s) in {config.SNAPSHOTS_DIR}")

    new_count = 0
    for path in files:
        if path.name in already:
            continue

        snapshot_time = parse_snapshot_time(path.name)
        if snapshot_time is None:
            print(f"  ! skipping {path.name}: no timestamp in filename")
            continue

        df = prepare_frame(read_snapshot(path), snapshot_time)
        con.register("incoming", df)
        con.execute("INSERT INTO market_snapshots SELECT * FROM incoming")
        con.unregister("incoming")
        con.execute(
            "INSERT INTO loaded_files VALUES (?, ?, ?, ?)",
            [path.name, snapshot_time, len(df), datetime.now()],
        )
        est = int(df["liquidity_is_estimated"].sum())
        print(
            f"  + {path.name}: {len(df):,} rows @ {snapshot_time:%Y-%m-%d %H:%M} "
            f"({est:,} liquidity values estimated)"
        )
        new_count += 1

    total = con.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
    snaps = con.execute(
        "SELECT COUNT(DISTINCT snapshot_time) FROM market_snapshots"
    ).fetchone()[0]
    con.close()

    print(
        f"\nLoaded {new_count} new file(s). "
        f"Store now holds {total:,} rows across {snaps} snapshot(s)."
    )


if __name__ == "__main__":
    main()
