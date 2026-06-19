"""
Turn Kalshi's long question titles into compact, readable labels.

Kalshi titles are full questions ("Will the New York win the 2026 Pro Basketball
Finals?") with a separate outcome ("New York"). For charts and tables we want a
short label that identifies the market at a glance, with the full title kept for
tooltips. The functions here do that, handling the phrasings that actually show
up in the data:

  * "Will (the) X win (the) Y?"        -> "Y — X"
  * "A vs B Winner?"                   -> "A vs B — <outcome>"
  * "<player>: <line> <stat>?"         -> title already holds the outcome
  * threshold markets (Bitcoin price)  -> outcome is the differentiator
  * everything else                    -> strip lead-in + "?", append outcome
"""

from __future__ import annotations

import re

# Lead-in phrases stripped from the front of a question (longest first).
_LEAD_INS = [
    "Will there be a ", "Will there be an ", "Will there be ",
    "Will the ", "Will a ", "Will an ", "Will ",
    "Does the ", "Does ", "Is the ", "Is there ", "Is ",
    "How many ", "What ",
]

# High-value compaction of verbose stock phrases (applied to the event part).
_SUBS = [
    (re.compile(r"\bFederal Reserve\b", re.I), "Fed"),
    (re.compile(r"\bLeague of Legends\b"), "LoL"),
    (re.compile(r"\s+at their\s+(.+?)\s+meeting", re.I), r" (\1)"),
    (re.compile(r"\bhike rates by\b", re.I), "hike"),
    (re.compile(r"\bcut rates by\b", re.I), "cut"),
    (re.compile(r"\bbasis points\b", re.I), "bps"),
    (re.compile(r"\bpresidential election\b", re.I), "election"),
]

_WIN_RE = re.compile(r"^(?:the\s+)?(?P<who>.+?)\s+(?:to\s+)?win\s+(?:the\s+)?(?P<event>.+)$", re.I)
_VS_WINNER_RE = re.compile(r"^(?P<match>.+?\bvs\.?\b.+?)\s+winner$", re.I)
_OUTCOME_ABOVE_RE = re.compile(r"\s+or (?:above|more|higher)$", re.I)


def _compact_outcome(outcome: str) -> str:
    """Shorten verbose outcome phrasings for use inside a compact label."""
    return _OUTCOME_ABOVE_RE.sub("+", outcome).strip()


def _strip_lead_in(text: str) -> str:
    for lead in _LEAD_INS:
        if text.lower().startswith(lead.lower()):
            return text[len(lead):]
    return text


def _compact(text: str) -> str:
    for pattern, repl in _SUBS:
        text = pattern.sub(repl, text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _truncate_keep_outcome(label: str, max_len: int, sep: str = " — ") -> str:
    """Truncate to max_len, preserving the outcome after ``sep`` when present."""
    if len(label) <= max_len:
        return label
    head, found, tail = label.rpartition(sep)
    if found and tail and len(tail) + len(sep) + 1 < max_len:
        keep = max_len - len(tail) - len(sep) - 1
        return head[:keep].rstrip() + "\u2026" + sep + tail
    return label[: max_len - 1].rstrip() + "\u2026"


def event_label(title: str, max_len: int = 40) -> str:
    """A compact label for the *event/theme* of a market, dropping the outcome.

    Used for series representatives ("what is this series about?").
    """
    base = (title or "").strip().rstrip("?").strip()
    base = _strip_lead_in(base)

    win = _WIN_RE.match(base)
    if win:
        base = win.group("event")
    else:
        vs = _VS_WINNER_RE.match(base)
        if vs:
            base = vs.group("match")

    base = _compact(base)
    base = _cap(base)
    if len(base) > max_len:
        base = base[: max_len - 1].rstrip() + "\u2026"
    return base


def clean_market_label(title: str, outcome: str = "", max_len: int = 46) -> str:
    """A compact label identifying a single market for charts and tables."""
    title = (title or "").strip()
    outcome = (outcome or "").strip()
    outcome_disp = _compact_outcome(outcome)
    base = _strip_lead_in(title.rstrip("?").strip())

    # "X win (the) Y" -> "Y — X"
    win = _WIN_RE.match(base)
    if win:
        who = _compact(win.group("who"))
        event = _compact(win.group("event"))
        return _truncate_keep_outcome(f"{_cap(event)} — {who}", max_len)

    # "A vs B Winner" -> "A vs B — outcome"
    vs = _VS_WINNER_RE.match(base)
    if vs:
        match = _compact(vs.group("match"))
        label = f"{_cap(match)} — {outcome_disp}" if outcome_disp else _cap(match)
        return _truncate_keep_outcome(label, max_len)

    base = _compact(base)

    # Append the outcome only when it adds information not already in the title.
    if outcome and outcome.lower() not in base.lower():
        return _truncate_keep_outcome(f"{_cap(base)} — {outcome_disp}", max_len)
    return _truncate_keep_outcome(_cap(base), max_len)
