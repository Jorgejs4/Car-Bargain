r"""One-shot: ingesta de un JSON de `NormalizedListing` en la base de datos (dev).

Uso (desde la raíz del repo):
    backend\.venv\Scripts\python.exe backend\scripts\ingest_listings_json.py data\wayback\mobile_de_20251205031456.json

El commit lo hace este script; por anuncio se crean/actualizan listings, se
anexa un snapshot (append-only) y se emiten los eventos de delta (igual que la
tarea Celery `scrape.mobile_de`, pero leyendo un JSON en vez de la red).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.ingest import ingest_listings
from scrapers.base.models import NormalizedListing


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta un JSON de NormalizedListing en la DB")
    parser.add_argument("json_file", help="Ruta al archivo JSON (lista de NormalizedListing)")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    listings = [NormalizedListing.model_validate(item) for item in payload]

    db = SessionLocal()
    try:
        result = ingest_listings(db, listings)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        f"OK: creados={result.listings_created} actualizados={result.listings_updated} "
        f"snapshots={result.snapshots_appended} eventos={result.events_emitted} omitidos={result.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
