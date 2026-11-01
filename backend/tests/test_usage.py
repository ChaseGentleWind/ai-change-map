"""模型费用统计测试。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.usage import record_usage, summarize_usage


def _record(model, created_at, result_count=1, metadata=None, status="completed"):
    return SimpleNamespace(
        model=model,
        created_at=created_at,
        result_urls=[f"/outputs/{index}.png" for index in range(result_count)],
        edit_metadata=metadata,
        status=status,
    )


def test_record_usage_uses_model_price_and_successful_image_count():
    record = _record("gpt-image-2-1k", datetime.now(), result_count=3)

    assert record_usage(record) == {"image_count": 3, "unit_price": 0.06, "cost": 0.18}


def test_record_usage_uses_recorded_model_price_after_fallback():
    record = _record(
        "gpt-image-2-4k-high",
        datetime.now(),
        result_count=2,
        metadata={"model_selection": {"model": "gpt-image-2-4k-high", "price_per_image": 0.2}},
    )

    assert record_usage(record)["cost"] == 0.4


def test_record_usage_ignores_legacy_usd_cost_and_reads_old_model_metadata():
    record = _record(
        "legacy-model-id",
        datetime.now(),
        result_count=2,
        metadata={"model_selection": {"price_per_image": 0.04}},
    )
    record.cost = 0.0004

    assert record_usage(record)["cost"] == 0.08


def test_summary_splits_today_from_all_and_ignores_failed_records():
    zone = timezone(timedelta(hours=8))
    now = datetime.now(zone)
    today = _record("gpt-image-2-1k", now, result_count=2)
    yesterday = _record("gpt-image-2-4k-high", now - timedelta(days=1), result_count=1)
    failed = _record("gpt-image-2-1k", now, result_count=1, status="failed")

    today_summary = summarize_usage([today, yesterday, failed], "today", today=now.date())
    all_summary = summarize_usage([today, yesterday, failed], "all", today=now.date())

    assert today_summary["cost"] == 0.12
    assert today_summary["image_count"] == 2
    assert all_summary["cost"] == 0.32
    assert all_summary["image_count"] == 3


def test_summary_treats_naive_database_timestamps_as_utc():
    zone = timezone(timedelta(hours=8))
    now = datetime(2026, 10, 31, 0, 30, tzinfo=zone)
    record = _record("gpt-image-2-1k", datetime(2026, 10, 30, 16, 30))

    result = summarize_usage([record], "today", today=now.date())

    assert result["image_count"] == 1
    assert result["cost"] == 0.06


@pytest.mark.asyncio
async def test_usage_endpoint_requires_auth_and_returns_empty_summary(client):
    unauthorized = await client.get("/api/usage")
    assert unauthorized.status_code == 401

    registered = await client.post(
        "/api/auth/register",
        json={"username": "费用统计用户", "phone": "13900000098", "password": "Password123"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    response = await client.get("/api/usage", params={"period": "all"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "period": "all",
        "currency": "CNY",
        "cost": 0,
        "image_count": 0,
        "models": [],
    }
