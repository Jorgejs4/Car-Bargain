from datetime import datetime, timezone
from decimal import Decimal

import pytest
from app.models import Listing, ListingSnapshot, ListingStatus
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError


def _make_listing(**overrides):
    data = {
        "source": "mobile_de",
        "source_listing_id": "123",
        "first_seen_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Listing(**data)


def test_unique_source_listing_id(db_session) -> None:
    db_session.add(_make_listing())
    db_session.commit()

    db_session.add(_make_listing())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_same_id_different_source_allowed(db_session) -> None:
    db_session.add(_make_listing(source="mobile_de", source_listing_id="1"))
    db_session.add(_make_listing(source="autoscout24", source_listing_id="1"))
    db_session.commit()

    count = db_session.scalar(select(func.count()).select_from(Listing))
    assert count == 2


def test_snapshots_are_append_only(db_session) -> None:
    listing = _make_listing()
    db_session.add(listing)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(ListingSnapshot(listing_id=listing.id, scraped_at=now, price=Decimal(10000)))
    db_session.add(ListingSnapshot(listing_id=listing.id, scraped_at=now, price=Decimal(9500)))
    db_session.commit()

    snapshots = db_session.scalars(
        select(ListingSnapshot).where(ListingSnapshot.listing_id == listing.id)
    ).all()
    assert len(snapshots) == 2
    assert {float(s.price) for s in snapshots} == {10000.0, 9500.0}


def test_invalid_status_rejected(db_session) -> None:
    listing = _make_listing(status="FOO")
    db_session.add(listing)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_default_status_active(db_session) -> None:
    listing = _make_listing()
    db_session.add(listing)
    db_session.commit()

    assert listing.status == ListingStatus.ACTIVE
