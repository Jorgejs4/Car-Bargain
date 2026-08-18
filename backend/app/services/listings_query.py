"""Consultas de lectura para la API REST (Fase 4).

Solo lectura y solo para el dashboard: por defecto se filtran listings
`ACTIVE` (regla del dominio: no mezclar datos live con históricos). Los
filtros de precio/km operan sobre el último snapshot de cada listing.
"""

import math
from collections import Counter
from decimal import Decimal

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models import Listing, ListingSnapshot, ListingStatus, Vehicle
from app.schemas.listing_event import ListingEventRead
from app.schemas.listing_snapshot import ListingSnapshotRead
from app.schemas.photo_analysis import PhotoAnalysisRead
from app.schemas.vehicle import VehicleRead

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100

_SORT_COLUMNS = {
    "price": lambda latest: latest.c.price,
    "mileage": lambda latest: latest.c.mileage,
    "year": lambda latest: Vehicle.year,
    "last_seen": lambda latest: Listing.last_seen_at,
    "bargain": lambda latest: Listing.bargain_score,
    "absolute_margin": lambda latest: Listing.absolute_margin,
    "cross_border": lambda latest: Listing.cross_border_margin,
    "total_cost": lambda latest: Listing.total_cost_es,
}


def _latest_snapshots_subquery():
    """Último snapshot por listing (DISTINCT ON listing_id, ordenado por scraped_at desc)."""
    return (
        select(ListingSnapshot)
        .distinct(ListingSnapshot.listing_id)
        .order_by(ListingSnapshot.listing_id, ListingSnapshot.scraped_at.desc())
        .subquery()
    )


def _build_conditions(
    latest,
    *,
    brand=None,
    model=None,
    variant=None,
    country=None,
    price_min=None,
    price_max=None,
    mileage_max=None,
    year_min=None,
    fuel=None,
    transmission=None,
    seller_type=None,
    status=None,
    source=None,
    region=None,
    needs_review=None,
    only_clean=False,
    vehicle_id=None,
    is_historical=None,
    min_bargain_score=None,
    min_absolute_margin=None,
    min_cross_border_margin=None,
):
    conditions = []
    if vehicle_id is not None:
        conditions.append(Listing.vehicle_id == vehicle_id)
    if brand:
        conditions.append(Vehicle.brand == brand)
    if model:
        conditions.append(Vehicle.model.ilike(f"%{model}%"))
    if variant:
        conditions.append(Vehicle.variant.ilike(f"%{variant}%"))
    if country:
        conditions.append(Listing.country == country.upper())
    if price_min is not None:
        conditions.append(latest.c.price >= Decimal(str(price_min)))
    if price_max is not None:
        conditions.append(latest.c.price <= Decimal(str(price_max)))
    if mileage_max is not None:
        conditions.append(latest.c.mileage <= mileage_max)
    if year_min is not None:
        conditions.append(Vehicle.year >= year_min)
    if fuel:
        conditions.append(Vehicle.fuel == fuel)
    if transmission:
        conditions.append(Vehicle.transmission == transmission)
    if seller_type:
        conditions.append(Listing.seller_type == seller_type)
    if status is not None:
        conditions.append(Listing.status == status)
    if source:
        conditions.append(Listing.source == source)
    if is_historical is not None:
        conditions.append(Listing.is_historical.is_(is_historical))
    elif status == ListingStatus.ACTIVE:
        conditions.append(Listing.is_historical.is_(False))
    if region:
        _eu_codes = {"DE", "FR", "IT", "NL", "BE", "AT", "LU"}
        if region.upper() == "ES":
            conditions.append(Listing.country == "ES")
        elif region.upper() == "EU":
            conditions.append(Listing.country.in_(_eu_codes))
    if needs_review is not None:
        conditions.append(Listing.needs_review == needs_review)
    if only_clean:
        # Solo entra en la pestaña de chollos una oferta con descripción
        # analizada, sin problema textual explícito, sin daño visual y sin
        # revisión pendiente. Los anuncios sin análisis quedan unknown.
        text_signals = Listing.text_signals
        conditions.extend(
            [
                Listing.needs_review.is_(False),
                text_signals.is_not(None),
                text_signals.contains({"deal_eligible": True}),
                or_(
                    Listing.photo_signals.is_(None),
                    ~Listing.photo_signals.contains({"has_visible_damage": True}),
                ),
            ]
        )
        comparable = aliased(Listing)
        comparable_count = (
            select(func.count(comparable.id))
            .where(
                comparable.vehicle_id == Listing.vehicle_id,
                comparable.status == ListingStatus.ACTIVE,
                comparable.is_historical.is_(False),
            )
            .correlate(Listing)
            .scalar_subquery()
        )
        conditions.append(comparable_count >= 3)
    if min_bargain_score is not None:
        conditions.append(Listing.bargain_score >= min_bargain_score)
    if min_absolute_margin is not None:
        conditions.append(Listing.absolute_margin >= min_absolute_margin)
    if min_cross_border_margin is not None:
        conditions.append(Listing.cross_border_margin >= min_cross_border_margin)
    return conditions


def _item(
    listing: Listing,
    vehicle: Vehicle | None,
    *,
    price,
    currency,
    mileage,
    title,
    condition_signals,
    raw_data=None,
    comparison_count=0,
) -> dict:
    """Monta una fila de lista a partir del listing, su vehículo y su último snapshot."""
    image_urls = (raw_data or {}).get("image_urls") or []
    if listing.is_historical:
        archive_reason = "Anuncio procedente de histórico"
    elif listing.status == ListingStatus.SOLD:
        archive_reason = "Marcado como vendido"
    elif listing.status in (ListingStatus.STALE, ListingStatus.REMOVED):
        archive_reason = "No localizado recientemente en la fuente"
    elif comparison_count < 3:
        archive_reason = "No hay suficientes unidades para comparar"
    else:
        archive_reason = None
    return {
        "id": listing.id,
        "source": listing.source,
        "source_listing_id": listing.source_listing_id,
        "url": listing.url,
        "seller_type": listing.seller_type,
        "country": listing.country,
        "status": listing.status,
        "is_historical": listing.is_historical,
        "brand": vehicle.brand if vehicle else None,
        "model": vehicle.model if vehicle else None,
        "generation": vehicle.generation if vehicle else None,
        "variant": vehicle.variant if vehicle else None,
        "year": vehicle.year if vehicle else None,
        "fuel": vehicle.fuel if vehicle else None,
        "transmission": vehicle.transmission if vehicle else None,
        "power_kw": vehicle.power_kw if vehicle else None,
        "title": title,
        "price": price,
        "currency": currency,
        "mileage": mileage,
        "image_urls": [str(url) for url in image_urls if url],
        "comparison_count": int(comparison_count or 0),
        "archive_reason": archive_reason,
        "condition_signals": condition_signals,
        "photo_signals": listing.photo_signals,
        "text_signals": listing.text_signals,
        "needs_review": listing.needs_review,
        "risk_score": listing.risk_score,
        "bargain_score": listing.bargain_score,
        "absolute_margin": listing.absolute_margin,
        "predicted_price": listing.predicted_price,
        "predicted_price_es": listing.predicted_price_es,
        "cross_border_margin": listing.cross_border_margin,
        "cross_border_score": listing.cross_border_score,
        "estimated_import_cost": listing.estimated_import_cost,
        "total_cost_es": listing.total_cost_es,
        "first_seen_at": listing.first_seen_at,
        "last_seen_at": listing.last_seen_at,
    }


def list_listings(
    session: Session,
    *,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    sort_by: str = "last_seen",
    sort_order: str = "desc",
    **filters,
) -> tuple[list[dict], int]:
    """Devuelve `(items, total)` de listings filtrados y paginados.

    Por defecto solo `status='ACTIVE'` y excluye históricos (regla del
    dashboard: no mezclar datos live con históricos). Pasar `status=None` para
    incluir cualquier estado, o `is_historical=True` para el archivo histórico.
    """
    latest = _latest_snapshots_subquery()
    comparable = aliased(Listing)
    comparison_count_expr = (
        select(func.count(comparable.id))
        .where(comparable.vehicle_id == Listing.vehicle_id, comparable.status == ListingStatus.ACTIVE, comparable.is_historical.is_(False))
        .correlate(Listing).scalar_subquery()
    )
    base = (
        select(
            Listing,
            Vehicle,
            latest.c.price,
            latest.c.currency,
            latest.c.mileage,
            latest.c.title,
            latest.c.condition_signals,
            latest.c.raw_data,
            comparison_count_expr,
        )
        .outerjoin(latest, latest.c.listing_id == Listing.id)
        .outerjoin(Vehicle, Vehicle.id == Listing.vehicle_id)
        .where(*_build_conditions(latest, **filters))
    )

    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0

    sort_col_fn = _SORT_COLUMNS.get(sort_by, _SORT_COLUMNS["last_seen"])
    sort_col = sort_col_fn(latest)
    order_clause = desc(sort_col) if sort_order == "desc" else asc(sort_col)
    rows = session.execute(
        base.order_by(order_clause.nullslast())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()

    items = [
        _item(
            listing,
            vehicle,
            price=price,
            currency=currency,
            mileage=mileage,
            title=title,
            condition_signals=condition_signals,
            raw_data=raw_data,
            comparison_count=comparison_count,
        )
        for listing, vehicle, price, currency, mileage, title, condition_signals, raw_data, comparison_count in rows
    ]
    return items, int(total)


def get_listing_detail(session: Session, listing_id: int) -> dict | None:
    """Detalle completo de un listing o `None` si no existe."""
    listing = session.scalar(
        select(Listing)
        .options(
            selectinload(Listing.vehicle),
            selectinload(Listing.snapshots),
            selectinload(Listing.events),
            selectinload(Listing.photo_analyses),
        )
        .where(Listing.id == listing_id)
    )
    if listing is None:
        return None

    latest = max(listing.snapshots, key=lambda s: s.scraped_at, default=None)
    data = _item(
        listing,
        listing.vehicle,
        price=latest.price if latest else None,
        currency=latest.currency if latest else None,
        mileage=latest.mileage if latest else None,
        title=latest.title if latest else None,
        condition_signals=latest.condition_signals if latest else None,
        raw_data=latest.raw_data if latest else None,
    )
    data["vehicle"] = VehicleRead.model_validate(listing.vehicle).model_dump() if listing.vehicle else None
    data["current_snapshot"] = (
        ListingSnapshotRead.model_validate(latest).model_dump() if latest else None
    )
    data["snapshots"] = [
        ListingSnapshotRead.model_validate(s).model_dump()
        for s in sorted(listing.snapshots, key=lambda s: s.scraped_at)
    ]
    data["events"] = [
        ListingEventRead.model_validate(e).model_dump()
        for e in sorted(listing.events, key=lambda e: e.event_timestamp, reverse=True)
    ]
    data["photo_analyses"] = [
        PhotoAnalysisRead.model_validate(p).model_dump()
        for p in sorted(listing.photo_analyses, key=lambda p: p.created_at)
    ]

    # Import breakdown para listings no-ES
    from app.engines.import_costs import estimate_for_listing

    if listing.country and listing.country != "ES" and latest and latest.price:
        estimate = estimate_for_listing(
            source_country=listing.country,
            price_eur=float(latest.price),
            co2_g_km=listing.vehicle.co2_g_km if listing.vehicle else None,
        )
        data["import_breakdown"] = {
            "source_country": estimate.source_country,
            "transport_cost": estimate.transport_cost,
            "registration_tax": estimate.registration_tax,
            "itv_inspection": estimate.itv_inspection,
            "registration_fees": estimate.registration_fees,
            "total_import_cost": estimate.total_import_cost,
            "total_cost_es": float(latest.price) + estimate.total_import_cost,
            "rules_version": estimate.rules_version,
        }

    # Estadísticas de mercado del vehículo
    if listing.vehicle_id is not None:
        market = vehicle_market(session, listing.vehicle_id)
        data["market"] = market

    return data


def vehicle_detail(session: Session, vehicle_id: int) -> dict | None:
    """Vehículo con sus listings ACTIVE, o `None` si no existe."""
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        return None
    items, _ = list_listings(
        session, vehicle_id=vehicle_id, status=ListingStatus.ACTIVE, page=1, page_size=PAGE_SIZE_MAX
    )
    data = VehicleRead.model_validate(vehicle).model_dump()
    data["listings"] = items
    return data


def vehicle_history(session: Session, vehicle_id: int) -> list[dict] | None:
    """Serie completa de snapshots (append-only) por anuncio del vehículo."""
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        return None

    entries = []
    for listing in sorted(vehicle.listings, key=lambda l: l.first_seen_at):
        snapshots = session.scalars(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == listing.id)
            .order_by(ListingSnapshot.scraped_at.asc())
        ).all()
        entries.append(
            {
                "listing_id": listing.id,
                "source": listing.source,
                "source_listing_id": listing.source_listing_id,
                "url": listing.url,
                "status": listing.status,
                "snapshots": [
                    {
                        "scraped_at": s.scraped_at,
                        "price": s.price,
                        "currency": s.currency,
                        "mileage": s.mileage,
                    }
                    for s in snapshots
                ],
            }
        )
    return entries


def _percentile(sorted_values: list[float], pct: int) -> float:
    """Percentil nearest-rank sobre una lista ordenada."""
    index = max(math.ceil(pct / 100 * len(sorted_values)) - 1, 0)
    return sorted_values[index]


def vehicle_market(session: Session, vehicle_id: int) -> dict | None:
    """Estadísticas del mercado del vehículo (precio del último snapshot, ACTIVE)."""
    if session.get(Vehicle, vehicle_id) is None:
        return None

    latest = _latest_snapshots_subquery()
    rows = session.execute(
        select(latest.c.price, latest.c.currency)
        .join(Listing, Listing.id == latest.c.listing_id)
        .where(
            Listing.vehicle_id == vehicle_id,
            Listing.status == ListingStatus.ACTIVE,
            latest.c.price.is_not(None),
        )
    ).all()

    values = sorted(float(price) for price, _ in rows)
    if not values:
        return {
            "vehicle_id": vehicle_id,
            "count": 0,
            "min_price": None,
            "p10": None,
            "p50": None,
            "p90": None,
            "max_price": None,
            "mean_price": None,
            "currency": None,
        }

    currency = None
    currencies = [c for _, c in rows if c]
    if currencies:
        currency = Counter(currencies).most_common(1)[0][0]

    total = sum(values)
    return {
        "vehicle_id": vehicle_id,
        "count": len(values),
        "min_price": round(values[0], 2),
        "p10": round(_percentile(values, 10), 2),
        "p50": round(_percentile(values, 50), 2),
        "p90": round(_percentile(values, 90), 2),
        "max_price": round(values[-1], 2),
        "mean_price": round(total / len(values), 2),
        "currency": currency,
    }


def list_brands(session: Session, *, q: str | None = None) -> list[str]:
    """Marcas distintas con al menos un listing ACTIVE y no histórico."""
    query = (
        select(Vehicle.brand)
        .join(Listing, Listing.vehicle_id == Vehicle.id)
        .where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.is_historical.is_(False),
        )
        .distinct()
        .order_by(Vehicle.brand.asc())
    )
    if q:
        query = query.where(Vehicle.brand.ilike(f"%{q}%"))
    return session.scalars(query).all()


def list_models(session: Session, *, brand: str) -> list[str]:
    """Modelos distintos para una marca con listings ACTIVE no históricos."""
    return (
        session.scalars(
            select(Vehicle.model)
            .join(Listing, Listing.vehicle_id == Vehicle.id)
            .where(
                Vehicle.brand == brand,
                Listing.status == ListingStatus.ACTIVE,
                Listing.is_historical.is_(False),
                Vehicle.model.is_not(None),
            )
            .distinct()
            .order_by(Vehicle.model.asc())
        ).all()
    )
