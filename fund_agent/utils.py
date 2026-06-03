from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def today_local() -> datetime:
    # 个人脚本不强依赖 timezone 库；系统时间通常已经够用。
    return datetime.now()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def safe_float(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return (a / b - 1.0) * 100.0


def date_range_lookback(days: int) -> tuple[str, str]:
    end = today_local()
    start = end - timedelta(days=days)
    return yyyymmdd(start), yyyymmdd(end)
