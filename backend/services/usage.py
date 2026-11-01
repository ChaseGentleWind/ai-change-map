"""按模型目录单价统计用户的人民币图片费用。"""
import json
from datetime import date, datetime, timedelta, timezone

from config import PROVIDERS_CONFIG

_BILLING_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")


def _parse_metadata(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
    return value if isinstance(value, dict) else {}


def _unit_price_by_model(model: str | None) -> float | None:
    if not model:
        return None
    for config in PROVIDERS_CONFIG.get("providers", {}).values():
        if config.get("model") == model and config.get("price_per_image") is not None:
            return float(config["price_per_image"])
    return None


def record_usage(record) -> dict:
    """读取新旧编辑记录，返回可用于账单统计的价格与张数。"""
    metadata = _parse_metadata(record.edit_metadata)
    selection = metadata.get("model_selection") or {}
    result_urls = record.result_urls
    if isinstance(result_urls, str):
        try:
            result_urls = json.loads(result_urls)
        except (TypeError, json.JSONDecodeError):
            result_urls = []
    image_count = len(result_urls) if isinstance(result_urls, list) else 0

    price = None
    if selection.get("price_per_image") is not None:
        price = float(selection["price_per_image"])
    if price is None:
        price = _unit_price_by_model(record.model)
    if not price or image_count <= 0:
        return {"image_count": 0, "unit_price": 0.0, "cost": 0.0}

    saved_cost = selection.get("total_cost_cny") if selection.get("currency") == "CNY" else None
    cost = float(saved_cost) if saved_cost is not None else round(price * image_count, 4)
    return {"image_count": image_count, "unit_price": price, "cost": cost}


def summarize_usage(records, period: str, today: date | None = None) -> dict:
    """汇总全部或北京时间当天的成功生图费用。"""
    today = today or datetime.now(_BILLING_TIMEZONE).date()
    model_totals: dict[str, dict] = {}
    total_cost = 0.0
    total_images = 0

    for record in records:
        if record.status != "completed":
            continue
        if period == "today":
            created_at = record.created_at
            if created_at is None:
                continue
            if created_at.tzinfo is None:
                # SQLite 与大多数 SQLAlchemy server_default 时间戳以 UTC 存储为无时区值。
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at.astimezone(_BILLING_TIMEZONE).date() != today:
                continue

        usage = record_usage(record)
        if not usage["image_count"]:
            continue
        model = record.model or "未知模型"
        group_key = f"{model}\0{usage['unit_price']:.4f}"
        item = model_totals.setdefault(group_key, {
            "model": model,
            "image_count": 0,
            "unit_price": usage["unit_price"],
            "cost": 0.0,
        })
        item["image_count"] += usage["image_count"]
        item["cost"] = round(item["cost"] + usage["cost"], 4)
        total_cost += usage["cost"]
        total_images += usage["image_count"]

    return {
        "period": period,
        "currency": "CNY",
        "cost": round(total_cost, 4),
        "image_count": total_images,
        "models": sorted(model_totals.values(), key=lambda item: item["cost"], reverse=True),
    }
