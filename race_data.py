"""Shared offline catalogue and payload validation (no network requests)."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

UTC = timezone.utc
SESSION_NAMES = {"R": "正賽 (Race)", "Q": "排位賽 (Qualifying)"}
COLUMNS = ["Time", "Distance", "Speed", "Throttle", "Brake", "X", "Y"]


def parse_utc(value):
    if not value:
        return None
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("賽程時間必須含時區")
    return date.astimezone(UTC)


def read_catalogue(path):
    catalogue = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(catalogue.get("year"), int) or not catalogue.get("events"):
        raise ValueError("賽程格式不完整")
    names = set()
    for event in catalogue["events"]:
        if not isinstance(event["event"], str) or event["event"] in names:
            raise ValueError("分站名稱重複或無效")
        names.add(event["event"])
        for code in SESSION_NAMES:
            parse_utc(event["sessions"][code]["start_utc"])
    return catalogue


def data_path(root, year, event, code):
    # Event names, not round numbers: rescheduling can change round numbers.
    slug = re.sub(r"[^a-z0-9]+", "_", event.lower()).strip("_")
    return Path(root) / "data" / f"{year}_{slug}_{code.lower()}.json"


def existing_path(root, year, event, code):
    path = data_path(root, year, event, code)
    if path.is_file():
        return path
    if (year, event, code) == (2026, "Australian Grand Prix", "R"):
        for legacy in [Path(root) / "2026_australia_race.json",
                       Path(root) / "data" / "2026_australia_race.json"]:
            if legacy.is_file():
                return legacy
    return path


def session_state(start_utc, now=None):
    """A schedule alone never proves completion; success needs a valid export."""
    now = now or datetime.now(UTC)
    start = parse_utc(start_utc)
    if start is None:
        return "unknown", "開賽時間尚未確認"
    if now < start:
        return "future", "尚未開賽"
    if now < start + timedelta(hours=6):
        return "waiting", "比賽進行中或資料整理中"
    return "missing", "已過預定開賽時間，資料尚未收錄"


def validate_payload(payload, expected=None):
    if not isinstance(payload, dict):
        raise ValueError("資料檔必須是 JSON 物件")
    identity = (payload.get("year"), payload.get("event"), payload.get("session"))
    if expected is not None and identity != tuple(expected):
        raise ValueError("資料檔的年份或場次不符")
    valid, skipped = {}, []
    if not isinstance(payload.get("drivers"), list):
        raise ValueError("缺少車手資料")
    for driver in payload["drivers"]:
        code = driver.get("code", "未知車手") if isinstance(driver, dict) else "未知車手"
        try:
            if not isinstance(driver, dict):
                raise ValueError("車手格式無效")
            if not isinstance(code, str) or not code or code in valid:
                raise ValueError("車手代碼無效或重複")
            lap_seconds = float(driver["lap_seconds"])
            if not np.isfinite(lap_seconds) or lap_seconds <= 0:
                raise ValueError("圈速無效")
            frame = pd.DataFrame(driver["telemetry"])[COLUMNS].copy()
            frame = frame.apply(pd.to_numeric, errors="raise")
            if len(frame) < 2 or not np.isfinite(frame.to_numpy(dtype=float)).all():
                raise ValueError("遙測缺少有效數值")
            if not (np.diff(frame["Time"]) > 0).all():
                raise ValueError("時間必須遞增")
            if not (np.diff(frame["Distance"]) > 0).all():
                raise ValueError("距離必須遞增")
            if frame["Time"].iloc[0] < -0.01 or abs(frame["Time"].iloc[-1] - lap_seconds) > 0.1:
                raise ValueError("遙測時間與圈速不符")
            if not frame["Brake"].isin([0, 1]).all():
                raise ValueError("煞車訊號無效")
            valid[code] = {"name": str(driver["name"]), "team": str(driver["team"]),
                           "lap_seconds": lap_seconds, "compound": str(driver.get("compound", "未知")),
                           "telemetry": frame}
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            skipped.append(f"{code}：{error}")
    if len(valid) < 2:
        raise ValueError("資料中可用車手不足兩位，請重新匯出")
    return (*identity, valid, skipped)


def read_payload(path, expected):
    return validate_payload(json.loads(Path(path).read_text(encoding="utf-8")), expected)
