"""Probe ICE report endpoints for London Cocoa (productId 37089076, marketId 7818845).

Run from backend/:
    .venv\\Scripts\\python diag_ice.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LONDON_PRODUCT_ID = "37089076"
LONDON_MARKET_ID = "7818845"

CANDIDATES = [
    "https://www.ice.com/products/37089076/London-Cocoa-Futures/data",
    f"https://www.ice.com/report/10?marketId={LONDON_MARKET_ID}",
    f"https://www.ice.com/report/10?productId={LONDON_PRODUCT_ID}",
    "https://www.ice.com/report/10",
    f"https://www.ice.com/report/176?marketId={LONDON_MARKET_ID}",
    f"https://www.ice.com/report/26?marketId={LONDON_MARKET_ID}",
]

OUT_DIR = Path(__file__).parent


def probe(fetcher, url: str):
    print(f"\n=== {url}")
    try:
        r = fetcher.fetch(url, headless=True, network_idle=True)
    except Exception as e:
        print(f"  fetch error: {type(e).__name__}: {e}")
        return None
    status = getattr(r, "status", "?")
    final = getattr(r, "url", "?")
    html = r.html_content if hasattr(r, "html_content") else str(r)
    print(f"  status: {status}")
    print(f"  final url: {final}")
    print(f"  length: {len(html)}")

    slug = re.sub(r"\W+", "_", url.replace("https://www.ice.com", ""))[:80]
    out = OUT_DIR / f"diag_ice__{slug}.html"
    out.write_text(html[:1_500_000], encoding="utf-8")
    print(f"  saved -> {out.name}")

    if hasattr(r, "css"):
        title = r.css("title")
        if title:
            print(f"  title: {title[0].text.clean()[:120]}")
        tables = r.css("table")
        print(f"  tables: {len(tables)}")
        for i, t in enumerate(tables[:3]):
            rows = t.css("tbody tr")
            headers = [th.text.clean()[:30] for th in t.css("thead th")]
            print(f"    [{i}] tbody_rows={len(rows)} headers={headers}")
            for j, tr in enumerate(rows[:6]):
                cells = []
                for td in tr.css("td"):
                    txt = td.text.clean()[:30]
                    cells.append(txt)
                print(f"        row[{j}]: {cells}")
    # Print select/dropdown options on report pages
    if hasattr(r, "css"):
        sels = r.css("select")
        for s in sels[:3]:
            opts = []
            for o in s.css("option"):
                val = o.attrib.get("value", "") if hasattr(o, "attrib") else ""
                txt = (o.text.clean() if hasattr(o, "text") else "").strip()
                opts.append(f"{val}={txt!r}")
            print(f"  select ({len(opts)} options): {opts[:8]}{' ...' if len(opts) > 8 else ''}")
    return r


def main() -> int:
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as e:
        print(f"scrapling not importable: {e}")
        return 1
    fetcher = StealthyFetcher(auto_match=True)
    for url in CANDIDATES:
        probe(fetcher, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
