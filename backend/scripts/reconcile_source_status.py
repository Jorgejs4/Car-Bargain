"""Reconcilia estados tras un barrido completo de una fuente.

Este comando debe ejecutarse solo cuando ``--max-pages`` cubra todas las páginas
de la fuente. Una ejecución parcial no debe modificar estados.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.ingest import ingest_listings
from app.services.status import update_listing_statuses
from scrapers.autoscout24.scraper import AutoScout24Scraper
from scrapers.coches_net.scraper import CochesNetScraper
from scrapers.mobile_de.scraper import MobileDeScraper


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconciliación segura de estados")
    parser.add_argument("source", choices=("mobile_de", "autoscout24", "coches_net"))
    parser.add_argument("--max-pages", type=int, required=True)
    parser.add_argument("--confirm-complete", action="store_true", help="Confirma que cubre todas las páginas")
    args = parser.parse_args()
    if not args.confirm_complete:
        parser.error("requiere --confirm-complete para evitar reconciliaciones parciales")

    scraper = {
        "mobile_de": MobileDeScraper,
        "autoscout24": AutoScout24Scraper,
        "coches_net": CochesNetScraper,
    }[args.source]()
    kwargs = {"country_codes": ["EU"]} if args.source == "autoscout24" else {}
    listings = scraper.run(max_pages=args.max_pages, **kwargs)
    if not listings:
        raise RuntimeError("barrido vacío; no se reconcilian estados")

    seen_ids = {listing.source_listing_id for listing in listings}
    with SessionLocal() as db:
        ingestion = ingest_listings(db, listings)
        result = update_listing_statuses(
            db,
            source=args.source,
            seen_source_listing_ids=seen_ids,
            run_complete=True,
        )
        db.commit()
    print(
        f"OK source={args.source} vistos={len(seen_ids)} "
        f"stale={result.stale} removed={result.removed} "
        f"creados={ingestion.listings_created} snapshots={ingestion.snapshots_appended}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
