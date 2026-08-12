import pytest

from app.models import (
    AlertPreference,
    Listing,
    ListingSnapshot,
    ListingStatus,
    Notification,
    NotificationStatus,
)
from app.services.alerts import evaluate_alerts


def _make_listing(db, **kwargs) -> Listing:
    defaults = {
        "source": "mobile_de",
        "source_listing_id": "x",
        "first_seen_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "status": ListingStatus.ACTIVE,
        "country": "DE",
        "is_historical": False,
    }
    defaults.update(kwargs)
    li = Listing(**defaults)
    db.add(li)
    db.flush()
    return li


def _make_snapshot(db, listing_id: int, **kwargs) -> ListingSnapshot:
    defaults = {
        "listing_id": listing_id,
        "scraped_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "price": 10000.0,
        "mileage": 50000,
    }
    defaults.update(kwargs)
    snap = ListingSnapshot(**defaults)
    db.add(snap)
    db.flush()
    return snap


def test_evaluate_no_preference_returns_zero(db_session) -> None:
    result = evaluate_alerts(db_session)
    assert result.checked == 0
    assert result.notified == 0


def test_evaluate_with_price_filter_excludes(db_session) -> None:
    pref = AlertPreference(user_key="me", max_purchase_price=5000.0)
    db_session.add(pref)
    db_session.flush()

    li = _make_listing(db_session)
    _make_snapshot(db_session, li.id, price=10000.0)
    db_session.commit()

    result = evaluate_alerts(db_session)
    assert result.checked == 1
    assert result.matched == 0
    assert result.notified == 0


def test_evaluate_with_matching_creates_notification(db_session) -> None:
    pref = AlertPreference(user_key="me", max_purchase_price=15000.0, min_profit=500.0)
    db_session.add(pref)
    db_session.flush()

    li = _make_listing(db_session)
    _make_snapshot(db_session, li.id, price=10000.0)
    li.absolute_margin = 1000.0
    db_session.commit()

    result = evaluate_alerts(db_session)
    assert result.matched == 1
    assert result.notified == 1
    assert db_session.query(Notification).count() == 1


def test_evaluate_dedupes_existing_notifications(db_session) -> None:
    pref = AlertPreference(user_key="me", max_purchase_price=15000.0)
    db_session.add(pref)
    db_session.flush()

    li = _make_listing(db_session)
    _make_snapshot(db_session, li.id, price=10000.0)
    db_session.commit()

    evaluate_alerts(db_session)
    db_session.commit()

    result = evaluate_alerts(db_session)
    assert result.deduped == 1
    assert result.notified == 0
    assert db_session.query(Notification).count() == 1


def test_evaluate_skips_non_active_and_historical(db_session) -> None:
    pref = AlertPreference(user_key="me", max_purchase_price=50000.0)
    db_session.add(pref)
    db_session.flush()

    li_removed = _make_listing(db_session, source="x1", source_listing_id="r", status=ListingStatus.REMOVED)
    _make_snapshot(db_session, li_removed.id, price=10000.0)
    li_hist = _make_listing(db_session, source="x2", source_listing_id="h", is_historical=True)
    _make_snapshot(db_session, li_hist.id, price=10000.0)
    db_session.commit()

    result = evaluate_alerts(db_session)
    assert result.checked == 0


def test_region_filter(db_session) -> None:
    pref = AlertPreference(user_key="me", region="ES")
    db_session.add(pref)
    db_session.flush()

    li_de = _make_listing(db_session, source="x1", source_listing_id="d", country="DE")
    _make_snapshot(db_session, li_de.id, price=10000.0)
    li_es = _make_listing(db_session, source="x2", source_listing_id="e", country="ES")
    _make_snapshot(db_session, li_es.id, price=10000.0)
    db_session.commit()

    result = evaluate_alerts(db_session)
    assert result.checked == 2
    assert result.notified == 1
    notif = db_session.query(Notification).one()
    assert notif.listing_id == li_es.id
