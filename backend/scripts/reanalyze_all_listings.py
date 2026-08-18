"""Reanaliza descripciones de listings desde el ordenador del operador.

Uso:
    backend\\.venv\\Scripts\\python.exe backend\\scripts\\reanalyze_all_listings.py --source coches_net --delay 1.0

El proceso escribe en la base configurada por DATABASE_URL/.env, por lo que si
esa URL apunta a la base online, el frontend online verá los resultados. No usa
Celery ni encola miles de tareas; procesa uno a uno y recalcula la valoración
al terminar.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.engines.valuation import score_all
from app.models import Listing, ListingStatus
from sqlalchemy import select
from workers.tasks import enrich_listing_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Reanaliza listings sin saturar Celery")
    parser.add_argument("--source", help="Fuente concreta; por defecto todas")
    parser.add_argument("--delay", type=float, default=1.0, help="Segundos entre anuncios")
    parser.add_argument("--limit", type=int, default=0, help="Límite; 0 = todos")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = select(Listing.id).where(
            Listing.status.in_([ListingStatus.ACTIVE, ListingStatus.STALE]),
            Listing.is_historical.is_(False),
        ).order_by(Listing.id)
        if args.source:
            query = query.where(Listing.source == args.source)
        if args.limit:
            query = query.limit(args.limit)
        ids = db.scalars(query).all()

    ok = failed = 0
    for index, listing_id in enumerate(ids, start=1):
        try:
            result = enrich_listing_text.run(listing_id)
            ok += int(result.get("status") == "done")
            failed += int(result.get("status") != "done")
        except Exception as exc:  # noqa: BLE001 - continúa con el lote
            failed += 1
            print(f"[{index}/{len(ids)}] {listing_id}: ERROR {exc}", file=sys.stderr)
        else:
            print(f"[{index}/{len(ids)}] {listing_id}: {result.get('status')}")
        if args.delay > 0 and index < len(ids):
            time.sleep(args.delay)

    with SessionLocal() as db:
        scoring = score_all(db)
        db.commit()

    print(f"Completado: seleccionados={len(ids)} ok={ok} fallidos={failed} scoring={scoring}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
