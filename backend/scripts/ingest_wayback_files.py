r"""Ingesta de listings históricos desde ficheros JSON sin red.

Lee los `NormalizedListing` guardados por `scrape_mobile_de_wayback.py` (u otros
dumps del mismo contrato) y los ingesta en la DB marcándolos `is_historical=True`.
Esto permite alimentar el pipeline sin depender del scrape en vivo.

Uso (desde la raíz del repo):
    backend\.venv\Scripts\python.exe backend\scripts\ingest_wayback_files.py [--glob data/wayback/*.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.ingest import ingest_listings
from scrapers.base.models import NormalizedListing


def load_listings(path: Path) -> list[NormalizedListing]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    listings = []
    for raw in payload:
        # Fuerza el flag histórico: estos dumps provienen de archivos, no del live.
        raw["is_historical"] = True
        listings.append(NormalizedListing.model_validate(raw))
    return listings


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta de dumps JSON históricos (Wayback)")
    parser.add_argument("--glob", default=str(Path("data") / "wayback" / "*.json"), help="Patrón de ficheros a ingestar")
    args = parser.parse_args()

    paths = sorted(Path().glob(args.glob))
    if not paths:
        print(f"No hay ficheros que coincidan con {args.glob}", file=sys.stderr)
        return 1

    total_created = total_updated = total_snapshots = 0
    db = SessionLocal()
    try:
        for path in paths:
            listings = load_listings(path)
            result = ingest_listings(db, listings)
            db.commit()
            total_created += result.listings_created
            total_updated += result.listings_updated
            total_snapshots += result.snapshots_appended
            print(
                f"{path.name}: {len(listings)} anuncios -> "
                f"{result.listings_created} creados, {result.listings_updated} actualizados"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Total: {total_created} creados, {total_updated} actualizados, {total_snapshots} snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
