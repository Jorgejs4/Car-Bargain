r"""One-shot: último snapshot de mobile.de vía Wayback → NormalizedListing JSON.

Uso (desde la raíz del repo):
    backend\.venv\Scripts\python.exe backend\scripts\scrape_mobile_de_wayback.py [--timestamp 20251205031456] [--out data\wayback]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.mobile_de.scraper import SEARCH_URL
from scrapers.mobile_de.wayback import (
    MobileDeHistoricalScraper,
    WaybackError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape histórico de mobile.de vía Wayback Machine")
    parser.add_argument("--url", default=SEARCH_URL, help="URL de búsqueda a capturar")
    parser.add_argument("--timestamp", default=None, help="Snapshot concreto (YYYYMMDDhhmmss); si no, el más reciente")
    parser.add_argument("--out", default=str(Path("data") / "wayback"), help="Directorio de salida")
    args = parser.parse_args()

    scraper = MobileDeHistoricalScraper()
    try:
        listings = scraper.run(args.url, args.timestamp) if args.timestamp else scraper.run_latest(args.url)
    except WaybackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = listings[0].scraped_at.strftime("%Y%m%d%H%M%S") if listings else datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out = out_dir / f"mobile_de_{stamp}.json"
    payload = [listing.model_dump(mode="json") for listing in listings]
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(listings)} anuncios guardados en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
