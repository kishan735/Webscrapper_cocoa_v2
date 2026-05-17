"""Tests for the resample helper used by /api/contract/{sym}/history."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.services.resample import resample_ohlc


@dataclass
class StubBar:
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    settle: Optional[float]
    volume: Optional[int]
    open_interest: Optional[int]


def _make_daily_bars(n: int, start: date) -> list[StubBar]:
    bars: list[StubBar] = []
    for i in range(n):
        d = start + timedelta(days=i)
        # Synthetic up-trend with a high/low band so OHLC isn't degenerate.
        c = 100.0 + i
        bars.append(
            StubBar(
                date=d,
                open=c - 0.5,
                high=c + 1.0,
                low=c - 1.0,
                settle=c,
                volume=10 * (i + 1),
                open_interest=1000 + i,
            )
        )
    return bars


def test_weekly_resample_aggregates_correctly():
    # 26 consecutive calendar days starting Mon 2024-01-01 → first 4 full
    # Mon-Fri weeks land Jan 5/12/19/26; days 27-28 spill into a 5th partial
    # bar, so we use 26 days to land cleanly on 4 weekly bars.
    bars = _make_daily_bars(26, date(2024, 1, 1))
    out = resample_ohlc(bars, "W")

    assert len(out) == 4

    # First weekly bar covers Mon-Fri = bars[0..4]
    wk1 = out[0]
    assert wk1["date"] == "2024-01-05"
    assert wk1["open"] == bars[0].open
    assert wk1["close"] == bars[4].settle
    assert wk1["high"] == max(b.high for b in bars[0:5])
    assert wk1["low"] == min(b.low for b in bars[0:5])
    assert wk1["volume"] == sum(b.volume for b in bars[0:5])
    # open_interest should be the LAST non-null value in the period
    assert wk1["open_interest"] == bars[4].open_interest


def test_monthly_resample_aggregates_correctly():
    # 60 days starting Jan 1 → spans Jan + Feb
    bars = _make_daily_bars(60, date(2024, 1, 1))
    out = resample_ohlc(bars, "M")
    assert len(out) == 2
    jan, feb = out
    assert jan["date"] == "2024-01-31"
    assert feb["date"] == "2024-02-29"  # 2024 is a leap year
    assert jan["open"] == bars[0].open
    assert jan["close"] == bars[30].settle  # Jan 31 is bars[30]


def test_empty_returns_empty():
    assert resample_ohlc([], "D") == []
    assert resample_ohlc([], "W") == []
    assert resample_ohlc([], "M") == []


def test_daily_passthrough_preserves_shape():
    bars = _make_daily_bars(3, date(2024, 1, 1))
    out = resample_ohlc(bars, "D")
    assert len(out) == 3
    assert out[0]["date"] == "2024-01-01"
    assert out[0]["close"] == bars[0].settle
    assert out[2]["volume"] == bars[2].volume
