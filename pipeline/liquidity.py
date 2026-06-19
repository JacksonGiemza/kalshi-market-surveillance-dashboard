"""
Liquidity normalisation — the single source of truth for the liquidity fix.

Both the ingestion loader and the (corrected) fetch script import from here so
the rule for "what number do we show in the liquidity column" is defined exactly
once. See config.py for the proxy weights and the reasoning behind them.
"""

from __future__ import annotations

import pandas as pd

import config


def add_liquidity_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with normalised liquidity columns added.

    Adds three columns:
      * ``liquidity_est``         the proxy estimate (always computed)
      * ``liquidity_is_estimated`` True where the real figure was unavailable
      * ``liquidity_eff``          the value the dashboard actually displays:
                                   the real figure when present, else the proxy

    The original ``liquidity_dollars`` column (the real figure, possibly 0) is
    left untouched so nothing downstream loses information.
    """
    out = df.copy()

    # Make sure the inputs exist and are numeric; missing columns become 0.
    for col in ("liquidity_dollars", "spread", "volume_24h", "oi"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    # Spread clipped to [0, 1] so the tightness factor stays sensible.
    tightness = (1.0 - out["spread"].clip(lower=0.0, upper=1.0)).clip(lower=0.0)

    out["liquidity_est"] = tightness * (
        config.LIQUIDITY_VOL_WEIGHT * out["volume_24h"]
        + config.LIQUIDITY_OI_WEIGHT * out["oi"].clip(lower=0.0)
    )

    real = out["liquidity_dollars"]
    out["liquidity_is_estimated"] = ~(real > 0)
    out["liquidity_eff"] = real.where(real > 0, out["liquidity_est"])

    return out
