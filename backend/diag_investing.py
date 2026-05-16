"""Dump Investing.com London Cocoa page structure for selector debugging.

Run from backend/ directory:
    .venv\\Scripts\\python diag_investing.py

Prints:
  - HTTP status
  - List of all <table> elements: row count + first row's text
  - Any element whose id/class contains 'contract'
  - Saves full HTML to diag_investing.html for inspection

Paste the stdout output back so we can pick the right selector.
"""
from __future__ import annotations

import sys
from pathlib import Path


URL = "https://www.investing.com/commodities/london-cocoa-contracts"
OUT_HTML = Path(__file__).parent / "diag_investing.html"
OUT_PREVIEW = Path(__file__).parent / "diag_investing_preview.txt"


def main() -> int:
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as e:
        print(f"scrapling not importable: {e}")
        return 1

    print(f"fetching: {URL}")
    fetcher = StealthyFetcher(auto_match=True)
    r = fetcher.fetch(URL, headless=True, network_idle=True)
    print(f"status: {r.status}")
    print(f"final url: {r.url if hasattr(r, 'url') else '?'}")
    print(f"html length: {len(r.html_content) if hasattr(r, 'html_content') else '?'}")

    OUT_HTML.write_text(r.html_content if hasattr(r, "html_content") else str(r), encoding="utf-8")
    print(f"full html saved to: {OUT_HTML}")

    print("\n--- TABLES ON PAGE ---")
    tables = r.css("table")
    print(f"found {len(tables)} <table> elements")
    for i, t in enumerate(tables):
        cls = t.attrib.get("class", "") if hasattr(t, "attrib") else ""
        tid = t.attrib.get("id", "") if hasattr(t, "attrib") else ""
        rows = t.css("tbody tr")
        first_cells = []
        if rows:
            first_cells = [td.text.clean()[:40] for td in rows[0].css("td")[:5]]
        print(f"  [{i}] id={tid!r} class={cls!r} tbody_rows={len(rows)} first_row={first_cells}")

    print("\n--- ANY 'contract' / 'cocoa' SELECTORS ---")
    for selector in [
        "[id*='contract']",
        "[class*='contract']",
        "[data-test*='contract']",
        "[id*='cocoa']",
        "[class*='instrument']",
        "[class*='crossRatesTbl']",
        "[data-test='instrument-price-last']",
    ]:
        hits = r.css(selector)
        if hits:
            print(f"  {selector!r:50s} -> {len(hits)} matches")
            for h in hits[:3]:
                txt = (h.text.clean() if hasattr(h, "text") else "")[:80]
                print(f"      sample: {txt}")

    print("\n--- TEXT PREVIEW (first 2000 chars after main content) ---")
    body_text = r.text.clean()[:2000] if hasattr(r, "text") else ""
    OUT_PREVIEW.write_text(body_text, encoding="utf-8")
    print(body_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
