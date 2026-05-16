"""Offline test for the Investing.com parser.

Runs the parser against a snapshot HTML saved by ``backend/diag_investing.py``.
The snapshot is committed so the test never hits the network.
"""
from pathlib import Path

from app.scrapers.investing import parse_investing_html

SNAPSHOT = Path(__file__).resolve().parents[1] / "diag_investing.html"


def test_parse_returns_six_plus_contracts():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_investing_html(html)
    assert len(rows) >= 6, f"expected >=6 contract rows, got {len(rows)}"

    symbols = [r.symbol for r in rows]
    assert all(s.startswith("LCCc") for s in symbols), f"unexpected symbols: {symbols}"
    assert "!" not in "".join(symbols), "continuous LCC1! should be filtered"


def test_front_three_have_price_and_volume():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_investing_html(html)
    for r in rows[:3]:
        assert r.last is not None and r.last > 0, f"{r.symbol} missing last"
        assert r.volume is not None and r.volume >= 0, f"{r.symbol} missing volume"
        assert r.contract_month, f"{r.symbol} missing contract_month label"


def test_contract_months_roll_forward():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_investing_html(html)
    months = [r.contract_month for r in rows]
    assert len(set(months)) == len(months), f"contract months not unique: {months}"


def test_front_month_has_open_interest():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_investing_html(html)
    assert rows[0].open_interest is not None and rows[0].open_interest > 0
