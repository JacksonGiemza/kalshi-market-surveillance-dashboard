"""Shared UI pieces used across pages (snapshot selector, header)."""

from __future__ import annotations

import streamlit as st

import config
import db
import theme


def snapshot_sidebar():
    """Render the sidebar snapshot picker and return the chosen time.

    The selection is keyed so it persists as the user moves between pages.
    With a single snapshot it's effectively fixed; as history accumulates this
    becomes the control that drives every page.
    """
    times = db.snapshot_times()
    with st.sidebar:
        st.markdown(f"### {config.APP_TITLE}")
        chosen = st.selectbox(
            "Snapshot",
            options=times,
            index=0,
            format_func=lambda t: t.strftime("%b %d, %Y · %H:%M UTC"),
            key="snapshot_choice",
        )
        if len(times) == 1:
            st.caption(
                "One snapshot loaded. Add more over time and trend views unlock here."
            )
    return chosen


def header(eyebrow: str, title: str, tagline: str | None = None) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    if tagline:
        st.markdown(f'<p class="tagline">{tagline}</p>', unsafe_allow_html=True)
