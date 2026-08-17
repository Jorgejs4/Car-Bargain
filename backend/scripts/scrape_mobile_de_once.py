r"""One-shot: prueba el scraping live de mobile.de desde la IP actual.

Guarda `listings_<ts>.json` y el raw de cada página. Códigos de salida:
0 = ok con anuncios, 1 = error de uso, 2 = bloqueado (403) por la fuente.

Uso (desde la raíz del repo):
    backend\.venv\Scripts\python.exe backend\scripts\scrape_mobile_de_once.py [--pages 1] [--out data\live]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.raw_store import save_raw
from scrapers.mobile_de.scraper import MobileDeScraper


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape one-shot de mobile.de (prueba live)")
    parser.add_argument("--pages", type=int, default=1, help="Número de páginas de resultados")
    parser.add_argument("--out", default=str(Path("data") / "live"), help="Directorio de salida")
    args = parser.parse_args()

    scraper = MobileDeScraper()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    def _save(page: int, html: str) -> None:
        save_raw(html, "mobile_de", f"srp_page_{page}.html")

    try:
        listings = scraper.run(max_pages=args.pages, on_page=_save)
    except RuntimeError as exc:
        print(f"BLOQUEADO: {exc}", file=sys.stderr)
        print("Sugerencia: ejecuta este script desde una IP no bloqueada (residencial) o configura SCRAPER_PROXY.", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mobile_de_{stamp}.json"
    payload = [listing.model_dump(mode="json") for listing in listings]
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: {len(listings)} anuncios guardados en {out}")
    for listing in listings[:3]:
        print(f"  - {listing.brand} {listing.model} {listing.year}: {listing.price} {listing.currency} ({listing.city}, {listing.country})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
