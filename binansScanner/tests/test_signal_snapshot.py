from datetime import datetime, timedelta, timezone

import pytest

from binansScanner.models.signal_snapshot import (
    MaterialChangePolicy,
    MaterialChangeReason,
    SignalIdentity,
    SignalSnapshot,
    SignalValidity,
    build_next_snapshot,
    evaluate_snapshot,
)


UTC = timezone.utc
T0 = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def identity() -> SignalIdentity:
    return SignalIdentity(symbol="BTCUSDT", strategy="momentum", intent="entry")


def snapshot(*, version=1, price=100.0, generated_at=T0, valid_until=None, confidence=0.8, quality=0.8, direction="BUY", decision="ENTRY_NOW", context="ctx-a") -> SignalSnapshot:
    return SignalSnapshot(
        identity=identity(),
        version=version,
        direction=direction,
        decision=decision,
        confidence=confidence,
        quality=quality,
        entry_plan={"entry_price": price, "mode": "limit"},
        generated_at=generated_at,
        valid_until=valid_until or generated_at + timedelta(hours=1),
        market_context_fingerprint=context,
    )


def test_identity_is_unique_and_deterministic():
    a = identity()
    b = SignalIdentity(symbol="BTCUSDT", strategy="momentum", intent="entry")
    c = SignalIdentity(symbol="BTCUSDT", strategy="mean-reversion", intent="entry")
    assert a.identity_key == b.identity_key
    assert a.identity_key != c.identity_key
    assert len(a.identity_key) == 64


def test_first_snapshot_is_version_one():
    relation = build_next_snapshot(
        previous=None,
        identity=identity(),
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.8,
        quality=0.8,
        entry_plan={"entry_price": 100.0},
        generated_at=T0,
        valid_until=T0 + timedelta(hours=1),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
    )
    assert relation.current.version == 1
    assert relation.previous is None
    assert not relation.material_change


def test_version_is_monotonic_and_previous_relation_is_explicit():
    v1 = snapshot()
    relation = build_next_snapshot(
        previous=v1,
        identity=v1.identity,
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.81,
        quality=0.81,
        entry_plan={"entry_price": 101.0},
        generated_at=T0 + timedelta(minutes=1),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        market_context_fingerprint="ctx-a",
    )
    assert relation.current.version == 2
    assert relation.previous_version == 1
    assert relation.current_version == 2
    assert not relation.material_change


def test_mandatory_buy_100_to_buy_118_is_stale():
    v1 = snapshot(price=100.0)
    relation = build_next_snapshot(
        previous=v1,
        identity=v1.identity,
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.8,
        quality=0.8,
        entry_plan={"entry_price": 118.0},
        generated_at=T0 + timedelta(minutes=5),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        market_context_fingerprint="ctx-a",
    )
    assert relation.material_change
    assert MaterialChangeReason.ENTRY_PRICE_CHANGED in relation.reasons
    assert evaluate_snapshot(relation.current, previous=v1, at=T0 + timedelta(minutes=5), policy=MaterialChangePolicy(entry_price_change_pct=0.10)) == SignalValidity.STALE


def test_direction_and_decision_changes_are_material():
    previous = snapshot()
    relation = build_next_snapshot(
        previous=previous,
        identity=previous.identity,
        direction="SELL",
        decision="SKIP",
        confidence=0.8,
        quality=0.8,
        entry_plan={"entry_price": 100.0},
        generated_at=T0 + timedelta(minutes=1),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        market_context_fingerprint="ctx-a",
    )
    assert MaterialChangeReason.DIRECTION_CHANGED in relation.reasons
    assert MaterialChangeReason.DECISION_CHANGED in relation.reasons


def test_market_context_and_threshold_crossing_are_material():
    previous = snapshot(confidence=0.40, quality=0.40, context="ctx-a")
    relation = build_next_snapshot(
        previous=previous,
        identity=previous.identity,
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.60,
        quality=0.60,
        entry_plan={"entry_price": 100.0},
        generated_at=T0 + timedelta(minutes=1),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(
            entry_price_change_pct=0.10,
            confidence_threshold=0.50,
            quality_threshold=0.50,
        ),
        market_context_fingerprint="ctx-b",
    )
    assert MaterialChangeReason.MARKET_CONTEXT_CHANGED in relation.reasons
    assert MaterialChangeReason.CONFIDENCE_THRESHOLD_CROSSED in relation.reasons
    assert MaterialChangeReason.QUALITY_THRESHOLD_CROSSED in relation.reasons


def test_expiry_is_explicit_and_not_stale_by_itself():
    current = snapshot(valid_until=T0 + timedelta(minutes=10))
    assert evaluate_snapshot(current, at=T0 + timedelta(minutes=9)) == SignalValidity.ACTIVE
    assert evaluate_snapshot(current, at=T0 + timedelta(minutes=10)) == SignalValidity.EXPIRED


def test_previous_expiry_at_new_generation_is_material():
    previous = snapshot(valid_until=T0 + timedelta(minutes=5))
    relation = build_next_snapshot(
        previous=previous,
        identity=previous.identity,
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.8,
        quality=0.8,
        entry_plan={"entry_price": 100.0},
        generated_at=T0 + timedelta(minutes=6),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        market_context_fingerprint="ctx-a",
    )
    assert MaterialChangeReason.VALIDITY_EXPIRED in relation.reasons
    assert relation.material_change


def test_no_fabricated_entry_price_fallback():
    previous = snapshot()
    relation = build_next_snapshot(
        previous=previous,
        identity=previous.identity,
        direction="BUY",
        decision="ENTRY_NOW",
        confidence=0.8,
        quality=0.8,
        entry_plan={"mode": "market"},
        generated_at=T0 + timedelta(minutes=1),
        valid_until=T0 + timedelta(hours=2),
        policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        market_context_fingerprint="ctx-a",
    )
    assert MaterialChangeReason.ENTRY_PRICE_CHANGED not in relation.reasons


def test_snapshot_is_immutable_and_timezones_are_normalized():
    value = snapshot()
    assert value.generated_at.tzinfo == UTC
    with pytest.raises(Exception):
        value.direction = "SELL"


def test_deterministic_canonical_payload():
    a = snapshot(price=100.0)
    b = snapshot(price=100.0)
    assert a.canonical_payload() == b.canonical_payload()


def test_identity_mismatch_is_rejected():
    previous = snapshot()
    other = SignalIdentity(symbol="ETHUSDT", strategy="momentum", intent="entry")
    with pytest.raises(ValueError, match="different signal identity"):
        build_next_snapshot(
            previous=previous,
            identity=other,
            direction="BUY",
            decision="ENTRY_NOW",
            confidence=0.8,
            entry_plan={"entry_price": 100.0},
            generated_at=T0 + timedelta(minutes=1),
            valid_until=T0 + timedelta(hours=2),
            policy=MaterialChangePolicy(entry_price_change_pct=0.10),
        )
