"""Offline test for the ICE London Cocoa Futures /data page parser.

Snapshot HTML is captured by ``backend/diag_ice.py``.
"""
from pathlib import Path

from app.scrapers.ice import parse_ice_data_html

SNAPSHOT = Path(__file__).resolve().parents[1] / "diag_ice___products_37089076_London_Cocoa_Futures_data.html"


def test_parses_at_least_six_contracts():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_ice_data_html(html)
    assert len(rows) >= 6, f"expected >=6 contract rows, got {len(rows)}"


def test_front_three_have_price_and_volume():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_ice_data_html(html)
    for r in rows[:3]:
        assert r.settle is not None and r.settle > 0, f"{r.symbol} missing settle"
        assert r.volume is not None and r.volume >= 0, f"{r.symbol} missing volume"
        assert r.change is not None, f"{r.symbol} missing change"
        assert r.contract_month, f"{r.symbol} missing contract_month label"


def test_contract_months_unique_and_well_formed():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_ice_data_html(html)
    months = [r.contract_month for r in rows]
    assert len(set(months)) == len(months), f"contract months not unique: {months}"
    for m in months:
        parts = m.split()
        assert len(parts) == 2 and len(parts[1]) == 4, f"malformed contract_month: {m!r}"


def test_as_of_date_parsed():
    html = SNAPSHOT.read_text(encoding="utf-8")
    rows = parse_ice_data_html(html)
    assert rows[0].as_of is not None, "expected as_of date to be parsed from Time(GMT) cell"
