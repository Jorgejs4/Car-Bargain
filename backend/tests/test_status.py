from datetime import datetime, timedelta, timezone

from app.models import Listing, ListingEvent, ListingEventType, ListingStatus
from app.services.status import update_listing_statuses
from sqlalchemy import select

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _add_listing(db_session, sid: str, *, last_seen: datetime, status: ListingStatus) -> None:
    db_session.add(
        Listing(
            source="mobile_de",
            source_listing_id=sid,
            first_seen_at=last_seen,
            last_seen_at=last_seen,
            status=status,
        )
    )


def _statuses(db_session) -> dict[str, str]:
    rows = db_session.scalars(select(Listing).order_by(Listing.source_listing_id)).all()
    return {row.source_listing_id: row.status.value for row in rows}


def test_active_older_than_removed_threshold_is_removed(db_session) -> None:
    _add_listing(db_session, "old", last_seen=NOW - timedelta(hours=60), status=ListingStatus.ACTIVE)
    db_session.commit()

    result = update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"old": "REMOVED"}
    assert result.checked == 1
    assert result.removed == 1

    event = db_session.scalar(select(ListingEvent))
    assert event.event_type == ListingEventType.REMOVED


def test_active_between_stale_and_removed_is_stale(db_session) -> None:
    _add_listing(db_session, "warm", last_seen=NOW - timedelta(hours=12), status=ListingStatus.ACTIVE)
    db_session.commit()

    result = update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"warm": "STALE"}
    assert result.stale == 1
    assert result.removed == 0

    event = db_session.scalar(select(ListingEvent))
    assert event.event_type == ListingEventType.STATUS_CHANGED


def test_fresh_listing_is_untouched(db_session) -> None:
    _add_listing(db_session, "fresh", last_seen=NOW - timedelta(hours=1), status=ListingStatus.ACTIVE)
    db_session.commit()

    result = update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"fresh": "ACTIVE"}
    assert result.checked == 1
    assert result.stale == 0
    assert result.removed == 0


def test_stale_older_than_removed_threshold_is_removed(db_session) -> None:
    _add_listing(db_session, "stale2", last_seen=NOW - timedelta(hours=60), status=ListingStatus.STALE)
    db_session.commit()

    update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"stale2": "REMOVED"}


def test_stale_not_old_enough_stays_stale(db_session) -> None:
    _add_listing(db_session, "stale1", last_seen=NOW - timedelta(hours=10), status=ListingStatus.STALE)
    db_session.commit()

    update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"stale1": "STALE"}


def test_sold_is_never_touched(db_session) -> None:
    _add_listing(db_session, "sold", last_seen=NOW - timedelta(hours=200), status=ListingStatus.SOLD)
    db_session.commit()

    update_listing_statuses(db_session, now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"sold": "SOLD"}
    assert db_session.scalar(select(ListingEvent)) is None


def test_filters_by_source(db_session) -> None:
    _add_listing(db_session, "old", last_seen=NOW - timedelta(hours=60), status=ListingStatus.ACTIVE)
    db_session.add(
        Listing(
            source="coches_net",
            source_listing_id="other",
            first_seen_at=NOW - timedelta(hours=60),
            last_seen_at=NOW - timedelta(hours=60),
            status=ListingStatus.ACTIVE,
        )
    )
    db_session.commit()

    result = update_listing_statuses(db_session, source="mobile_de", now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"old": "REMOVED", "other": "ACTIVE"}
    assert result.removed == 1


def test_per_source_thresholds_override_globals(monkeypatch, db_session) -> None:
    from app.services import status as status_module

    monkeypatch.setattr(
        status_module.settings,
        "status_thresholds_json",
        '{"mobile_de": {"stale_after_hours": 1, "removed_after_hours": 2}}',
    )
    _add_listing(db_session, "h15", last_seen=NOW - timedelta(hours=1.5), status=ListingStatus.ACTIVE)
    _add_listing(db_session, "h3", last_seen=NOW - timedelta(hours=3), status=ListingStatus.ACTIVE)
    db_session.commit()

    update_listing_statuses(db_session, source="mobile_de", now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"h15": "STALE", "h3": "REMOVED"}


def test_invalid_thresholds_json_is_ignored(monkeypatch, db_session) -> None:
    from app.services import status as status_module

    monkeypatch.setattr(status_module.settings, "status_thresholds_json", "{not json")
    _add_listing(db_session, "old", last_seen=NOW - timedelta(hours=60), status=ListingStatus.ACTIVE)
    db_session.commit()

    update_listing_statuses(db_session, source="mobile_de", now=NOW)
    db_session.commit()

    assert _statuses(db_session) == {"old": "REMOVED"}
