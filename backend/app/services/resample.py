"""Resample daily OHLCV bars to weekly or monthly bars.

Aggregations:
    open  = first non-null bar in the period
    high  = max
    low   = min
    close = last non-null bar
    volume = sum
    open_interest = last non-null bar

Weekly anchors to Friday (W-FRI). Monthly anchors to month-end (ME).
"""
from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

_RULES = {
    "D": None,
    "W": "W-FRI",
    "M": "ME",
}


def _row(date_val: _date, o, h, l, c, v, oi) -> Dict[str, Any]:
    def _f(x) -> Optional[float]:
        return None if x is None or pd.isna(x) else float(x)

    def _i(x) -> Optional[int]:
        return None if x is None or pd.isna(x) else int(x)

    return {
        "date": date_val.isoformat(),
        "open": _f(o),
        "high": _f(h),
        "low": _f(l),
        "close": _f(c),
        "volume": _i(v),
        "open_interest": _i(oi),
    }


def resample_ohlc(rows: Iterable[Any], tf: str) -> List[Dict[str, Any]]:
    """Resample a sequence of QuoteEod rows (asc by date) to the requested timeframe.

    ``rows`` must expose ``.date, .open, .high, .low, .settle, .volume, .open_interest``.
    Returns a list of dicts shaped like the existing /history payload.
    """
    rule = _RULES.get(tf.upper())
    rows = list(rows)
    if rule is None:
        return [
            _row(r.date, r.open, r.high, r.low, r.settle, r.volume, r.open_interest)
            for r in rows
        ]
    if not rows:
        return []
    df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(r.date),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.settle,
                "volume": r.volume,
                "open_interest": r.open_interest,
            }
            for r in rows
        ]
    ).set_index("date").sort_index()
    agg = df.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "open_interest": "last",
        }
    )
    agg = agg.dropna(subset=["close"])
    return [
        _row(ts.date(), row["open"], row["high"], row["low"], row["close"], row["volume"], row["open_interest"])
        for ts, row in agg.iterrows()
    ]
