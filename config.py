"""
Central configuration for the Kalshi markets dashboard.

Everything that someone might reasonably want to tune — paths, the liquidity
proxy weights, default chart sizes — lives here so the rest of the code never
hard-codes a magic number. Edit this file, not the modules that read it.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"      # raw snapshot files land here
DB_PATH = DATA_DIR / "kalshi.duckdb"        # built by pipeline/load_snapshots.py

# Snapshot filenames look like: kalshi_markets_YYYYMMDD_HHMMSS.csv  (or .parquet)
SNAPSHOT_GLOBS = ("kalshi_markets_*.csv", "kalshi_markets_*.parquet")
SNAPSHOT_FILENAME_RE = r"kalshi_markets_(\d{8}_\d{6})"
SNAPSHOT_TIME_FORMAT = "%Y%m%d_%H%M%S"

# ---------------------------------------------------------------------------
# Liquidity proxy
# ---------------------------------------------------------------------------
# Kalshi's API exposes a real "liquidity" figure (dollar value resting on the
# order book). When that value is present and positive we use it as-is. When it
# is missing or zero — as it is in the seed snapshot — we fall back to a
# transparent ESTIMATE built from fields we do have. The estimate is clearly
# flagged everywhere it surfaces; it is a ranking aid, not a quoted book depth.
#
#   liquidity_est = (1 - spread) * (VOL_WEIGHT * volume_24h + OI_WEIGHT * oi)
#
# Rationale: tighter spreads and more recent traded notional / open interest all
# indicate a more liquid market. The (1 - spread) factor discounts markets whose
# wide quotes make their nominal size hard to actually trade against.
LIQUIDITY_VOL_WEIGHT = 0.75
LIQUIDITY_OI_WEIGHT = 0.25

# ---------------------------------------------------------------------------
# Display defaults
# ---------------------------------------------------------------------------
DEFAULT_TOP_N = 15
APP_TITLE = "Kalshi Markets"
APP_TAGLINE = "Open-interest, liquidity and price movement across live markets"
