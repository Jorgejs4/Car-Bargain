from datetime import datetime, timezone

from app.models import Listing, ListingEvent, ListingEventType, ListingStatus
from app.services.status import update_listing_statuses
from sqlalchemy import select

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _add_listing(db_session, sid: str, *, status: ListingStatus) -> None:
    db_session.add(
        Listing(
            source="mobile_de",
            source_listing_id=sid,
            first_seen_at=NOW,
            last_seen_at=NOW,
            status=status,
        )
    )


def _statuses(db_session) -> dict[str, str]:
    rows = db_session.scalars(select(Listing).order_by(Listing.source_listing_id)).all()
    return {row.source_listing_id: row.status.value for row in rows}


def _run(db_session, seen: set[str], *, source: str = "mobile_de"):
    result = update_listing_statuses(
        db_session,
        source=source,
        seen_source_listing_ids=seen,
        run_complete=True,
        now=NOW,
    )
    db_session.commit()
    return result


def test_missing_once_does_not_change_status(db_session) -> None:
    _add_listing(db_session, "one", status=ListingStatus.ACTIVE)
    db_session.commit()

    result = _run(db_session, set())

    assert _statuses(db_session) == {"one": "ACTIVE"}
    assert result.stale == 0
    assert db_session.scalar(select(Listing)).consecutive_misses == 1


def test_three_complete_misses_mark_stale(db_session) -> None:
    _add_listing(db_session, "one", status=ListingStatus.ACTIVE)
    db_session.commit()

    for _ in range(3):
        result = _run(db_session, set())

    assert _statuses(db_session) == {"one": "STALE"}
    assert result.stale == 1
    assert db_session.scalar(select(ListingEvent)).event_type == ListingEventType.STATUS_CHANGED


def test_eight_complete_misses_mark_removed(db_session) -> None:
    _add_listing(db_session, "one", status=ListingStatus.ACTIVE)
    db_session.commit()

    for _ in range(8):
        result = _run(db_session, set())

    assert _statuses(db_session) == {"one": "REMOVED"}
    assert result.removed == 1


def test_reappearance_resets_misses_and_reactivates_stale(db_session) -> None:
    _add_listing(db_session, "one", status=ListingStatus.STALE)
    db_session.commit()
    listing = db_session.scalar(select(Listing))
    listing.consecutive_misses = 4
    db_session.commit()

    _run(db_session, {"one"})

    listing = db_session.scalar(select(Listing))
    assert listing.status == ListingStatus.ACTIVE
    assert listing.consecutive_misses == 0
    assert listing.last_verified_at == NOW
    assert db_session.scalar(select(ListingEvent)).event_type == ListingEventType.REAPPEARED


def test_incomplete_run_does_not_change_status(db_session) -> None:
    _add_listing(db_session, "one", status=ListingStatus.ACTIVE)
    db_session.commit()

    result = update_listing_statuses(db_session, seen_source_listing_ids=set(), run_complete=False, now=NOW)

    assert _statuses(db_session) == {"one": "ACTIVE"}
    assert result.checked == 0


def test_sold_is_never_touched(db_session) -> None:
    _add_listing(db_session, "sold", status=ListingStatus.SOLD)
    db_session.commit()

    _run(db_session, set())

    assert _statuses(db_session) == {"sold": "SOLD"}
    assert db_session.scalar(select(ListingEvent)) is None


def test_filters_by_source(db_session) -> None:
    _add_listing(db_session, "mobile", status=ListingStatus.ACTIVE)
    db_session.add(
        Listing(
            source="coches_net",
            source_listing_id="coches",
            first_seen_at=NOW,
            last_seen_at=NOW,
            status=ListingStatus.ACTIVE,
        )
    )
    db_session.commit()

    for _ in range(3):
        _run(db_session, set(), source="mobile_de")

    assert _statuses(db_session) == {"coches": "ACTIVE", "mobile": "STALE"}
