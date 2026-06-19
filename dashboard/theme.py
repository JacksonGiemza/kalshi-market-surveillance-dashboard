"""
Visual identity and formatting helpers.

One palette, one type system, one set of formatters — imported everywhere so
the dashboard reads as a single deliberate instrument rather than a stack of
default widgets. Numbers are the subject here, so they get a monospaced face and
consistent money / probability formatting.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Palette  (warm-neutral paper, deep indigo ink, one confident teal accent)
# ---------------------------------------------------------------------------
INK = "#16161F"
PAPER = "#FBFAF7"
SURFACE = "#FFFFFF"
MUTED = "#7C786C"
GRID = "#ECE7DE"
ACCENT = "#0E7C66"     # teal — probability / "yes" / primary
UP = "#0E7C66"         # gains
DOWN = "#C0492F"       # losses (muted clay, not alarm red)
HALO = "#E6F0EC"       # faint accent wash for fills

SANS = "'IBM Plex Sans', system-ui, sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, monospace"


def inject_css() -> None:
    """Load fonts and apply the type / spacing treatment once per page."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"], .stApp {{
            font-family: {SANS};
            color: {INK};
        }}
        .stApp {{ background: {PAPER}; }}

        /* Numbers — metrics, tables and code-ish values — get the mono face */
        [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {{
            font-family: {MONO};
            font-feature-settings: "tnum" 1;
        }}
        [data-testid="stMetricValue"] {{ font-weight: 600; }}
        [data-testid="stMetricLabel"] {{
            text-transform: uppercase;
            letter-spacing: .07em;
            font-size: .72rem;
            color: {MUTED};
        }}

        h1, h2, h3 {{ font-weight: 600; letter-spacing: -.01em; }}

        /* The eyebrow above the title encodes the snapshot, not decoration */
        .eyebrow {{
            font-family: {MONO};
            font-size: .78rem;
            letter-spacing: .12em;
            text-transform: uppercase;
            color: {ACCENT};
            margin-bottom: .15rem;
        }}
        .tagline {{ color: {MUTED}; margin-top: -.4rem; font-size: 1rem; }}

        hr {{ border-color: {GRID}; }}
        [data-testid="stDataFrame"] {{ font-family: {MONO}; }}

        /* Clear Streamlit's fixed header so the eyebrow/title aren't clipped */
        .block-container {{ padding-top: 4.5rem; }}
        .eyebrow {{ padding-top: .1rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(fig, *, height: int | None = None):
    """Apply the house style to a Plotly figure in place and return it."""
    fig.update_layout(
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=64, t=10, b=8),
        colorway=[ACCENT, DOWN, MUTED, INK],
        hoverlabel=dict(font_family="IBM Plex Mono, monospace"),
        showlegend=False,
    )
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    return fig


def bar_range(values, frac: float = 0.28) -> list[float]:
    """An x-axis range for a horizontal bar chart that leaves room for the
    outside value labels, padding on whichever side(s) the bars extend."""
    vals = [float(v) for v in values] or [0.0]
    vmin, vmax = min(vals), max(vals)
    amax = max(abs(vmin), abs(vmax), 1.0)
    pad = amax * frac
    lo = (vmin - pad) if vmin < 0 else 0.0
    hi = (vmax + pad) if vmax > 0 else 0.0
    return [lo, hi]


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
def money(x: float) -> str:
    """Compact dollar string: 27646341 -> '$27.6M'."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if x < 0 else ""
    x = abs(x)
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= threshold:
            return f"{sign}${x / threshold:.1f}{suffix}"
    return f"{sign}${x:,.0f}"


def price_cents(x: float) -> str:
    """A yes price (dollars, 0–1) shown as cents: 0.80 -> '80\u00a2'."""
    try:
        return f"{round(float(x) * 100)}\u00a2"
    except (TypeError, ValueError):
        return "—"


def change_cents(x: float) -> str:
    """Signed 24h change in cents: 0.18 -> '+18\u00a2', -0.05 -> '\u221215\u00a2'."""
    try:
        c = round(float(x) * 100)
    except (TypeError, ValueError):
        return "—"
    if c > 0:
        return f"+{c}\u00a2"
    if c < 0:
        return f"\u2212{abs(c)}\u00a2"
    return "0\u00a2"
