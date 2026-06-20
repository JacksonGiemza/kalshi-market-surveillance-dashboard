# Kalshi Markets Dashboard

A shareable Streamlit dashboard over Kalshi market data — open interest,
liquidity, prices and 24h movement across every open market. Built snapshot-first
but **history-ready**: every snapshot is stored with its timestamp, so trend
views can be switched on later with no change to ingestion.

---

https://kalshi-market-surveillance-dashboard-dmeh9hwayzu5f2gdefghtf.streamlit.app/

## Quickstart

```bash
pip install -r requirements.txt
streamlit run dashboard/Overview.py
```

The repo ships with one seed snapshot already loaded, so the app runs
immediately. To start from scratch instead:

```bash
python pipeline/load_snapshots.py      # build the store from data/snapshots/
streamlit run dashboard/Overview.py
```

---

## How it works

The pipeline is split into three layers so each can grow independently — add a
visualization without touching ingestion, add a data source without touching the
UI.

```
 fetch_kalshi.py        load_snapshots.py            dashboard/
 ───────────────        ─────────────────            ──────────
 Kalshi API  ──▶  data/snapshots/*.csv|.parquet ──▶  DuckDB  ──▶  Streamlit
   (capture)          (timestamped raw)          (market_snapshots)   (read)
```

1. **Ingest** — `pipeline/fetch_kalshi.py` pulls all open markets and writes a
   timestamped `kalshi_markets_<ts>.csv` **and** `.parquet` into
   `data/snapshots/`.
2. **Store** — `pipeline/load_snapshots.py` appends each new snapshot into a
   DuckDB table `market_snapshots`, keyed by `(ticker, snapshot_time)`. It's
   incremental and idempotent: each file loads once, tracked in `loaded_files`.
3. **Present** — the Streamlit app reads pre-shaped queries ("marts") from
   `dashboard/db.py`. Today it shows the latest snapshot; the snapshot selector
   in the sidebar is the hook for time-series views.

### Pages
- **Overview** — headline KPIs, largest markets by open interest, concentration
  by series, biggest 24h moves. For the view-only audience.
- **Explore** — two tabs. *Markets*: search, series/liquidity filters, a sortable
  formatted table and CSV export. *Series breakdown*: every series rolled up and
  ranked by total volume (switchable to 24h volume, open interest, liquidity or
  market count), with a leaders chart and a sortable, exportable table. For
  analysts.
- **About** — definitions, the liquidity methodology, and the roadmap.

---

## The liquidity fix

The original export produced a `liquidity_dollars` column that was **0 for every
row**. Two changes address it:

- **`pipeline/fetch_kalshi.py`** now captures liquidity correctly: it prefers the
  real dollar value, falls back to Kalshi's `liquidity` field (reported in
  *cents*, so divided by 100), and only leaves 0 when neither is present. Re-run
  the fetch to populate real values.
- **`pipeline/liquidity.py`** defines a transparent **estimate** used when the
  real figure is missing (as in the seed snapshot):

  ```
  liquidity_est = (1 - spread) × (0.75 · volume_24h + 0.25 · open_interest)
  ```

  Tighter spreads and more traded notional / open interest indicate a more liquid
  market; the spread factor discounts markets whose wide quotes make their size
  hard to trade against. Estimated values are **flagged everywhere they appear**
  (an asterisk in tables, a banner on Overview, full detail on About), and the
  weights live in `config.py`. It's a ranking aid, not a quoted book depth.

Whenever a snapshot carries a real liquidity figure, that value is used and the
estimate is ignored — no code change needed.

---

## Adding data over time

Run the fetch on a schedule (cron, Task Scheduler, a CI job) and load:

```bash
python pipeline/fetch_kalshi.py && python pipeline/load_snapshots.py
```

Each run adds a snapshot. The store grows append-only; nothing is overwritten.
Once several snapshots exist, the sidebar selector lets you move between them —
the natural place to add probability-drift and liquidity-build-up charts.

---

## Configuration

Everything tunable lives in `config.py`: file paths, the liquidity proxy weights,
default chart sizes. Edit it there rather than in the modules.

Theme (colors, fonts) is in `dashboard/theme.py` and `.streamlit/config.toml`.

---

## Sharing with stakeholders

- **Fastest:** [Streamlit Community Cloud](https://streamlit.io/cloud) — push to a
  Git repo and deploy; supports a simple password gate for a small audience.
- **Internal/sensitive data:** run behind your own SSO / reverse proxy, or host on
  an internal VM. The app is a standard Streamlit process (`streamlit run`).

If you deploy to a shared host, schedule the fetch+load there (or sync the
`data/` directory) so the dashboard stays current.

---

## Project layout

```
kalshi-dashboard/
├── config.py                  # paths + tunable parameters (single source)
├── requirements.txt
├── .streamlit/config.toml     # theme
├── pipeline/
│   ├── fetch_kalshi.py        # corrected capture (liquidity + parquet)
│   ├── liquidity.py           # shared liquidity normalisation
│   └── load_snapshots.py      # incremental DuckDB loader
├── dashboard/
│   ├── Overview.py            # entry point — run this
│   ├── db.py                  # query layer / marts
│   ├── theme.py               # palette, CSS, formatters
│   ├── labels.py              # market/series name cleaning
│   ├── ui.py                  # shared header + snapshot selector
│   └── pages/
│       ├── 1_Explore.py
│       └── 2_About.py
└── data/
    ├── snapshots/             # raw timestamped snapshots (seeded)
    └── kalshi.duckdb          # the store (prebuilt; regenerable)
```
