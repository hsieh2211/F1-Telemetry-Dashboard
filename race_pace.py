"""Versioned, offline lap records; no FastF1 requests or inferred race results."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from race_data import data_path, parse_utc

TIME_FIELDS = {
    "lap_seconds": "LapTime", "start_seconds": "LapStartTime", "end_seconds": "Time",
    "pit_in_seconds": "PitInTime", "pit_out_seconds": "PitOutTime",
    "sector1_seconds": "Sector1Time", "sector2_seconds": "Sector2Time", "sector3_seconds": "Sector3Time",
}
BOOL_FIELDS = {"accurate": "IsAccurate", "deleted": "Deleted", "fresh_tyre": "FreshTyre", "generated": "FastF1Generated"}
NUMBER_FIELDS = {"stint": "Stint", "tyre_life": "TyreLife", "position": "Position"}


def laps_path(root, year, event, code):
    return data_path(root, year, event, code).with_suffix(".laps.json")


def _missing(value):
    return value is None or bool(pd.isna(value))


def export_laps(session, year, event, code, version):
    """Serialize all recorded laps, including null times and uncertain flags."""
    if code not in ("R", "S"):
        raise ValueError("逐圈節奏匯出僅支援正賽與衝刺賽")
    if "Finalised" not in set(session.session_status["Status"].astype(str)):
        raise ValueError("尚未確認場次結束（缺少 Finalised），稍後再試")
    roster = [{"code": str(r["Abbreviation"]), "name": str(r["FullName"]), "team": str(r["TeamName"])}
              for _, r in session.results.iterrows()]
    records, omitted = [], 0
    for _, row in session.laps.iterrows():
        number, driver = row.get("LapNumber"), row.get("Driver")
        if _missing(number) or _missing(driver):
            omitted += 1
            continue
        record = {"driver": str(driver), "lap": float(number)}
        for target, source in TIME_FIELDS.items():
            value = row.get(source)
            record[target] = None if _missing(value) else float(value.total_seconds())
        for target, source in NUMBER_FIELDS.items():
            value = row.get(source)
            record[target] = None if _missing(value) else float(value)
        for target, source in BOOL_FIELDS.items():
            value = row.get(source)
            if not _missing(value) and not isinstance(value, (bool, np.bool_)):
                raise ValueError(f"{source} 不是布林值")
            record[target] = None if _missing(value) else bool(value)
        for target, source in (("compound", "Compound"), ("track_status", "TrackStatus")):
            value = row.get(source)
            record[target] = None if _missing(value) or str(value).strip() == "" else str(value)
        records.append(record)
    payload = {"schema_version": 1, "kind": "race_laps", "year": year, "event": event, "session": code,
               "session_finalised": True, "source": "FastF1", "fastf1_version": version,
               "exported_at": datetime.now(timezone.utc).isoformat(), "drivers": roster,
               "laps": records, "omitted_rows": omitted}
    validate_laps(payload, (year, event, code))
    return payload


def validate_laps(payload, expected):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("kind") != "race_laps":
        raise ValueError("逐圈檔案版本或格式不符")
    if (payload.get("year"), payload.get("event"), payload.get("session")) != tuple(expected):
        raise ValueError("逐圈資料的年份或場次不符")
    if payload.get("session") not in ("R", "S") or payload.get("session_finalised") is not True:
        raise ValueError("逐圈資料尚未確認完賽或不支援此場次")
    if not isinstance(payload.get("exported_at"), str) or parse_utc(payload["exported_at"]) is None:
        raise ValueError("逐圈匯出時間無效")
    if not isinstance(payload.get("drivers"), list) or not isinstance(payload.get("laps"), list) or not payload["laps"]:
        raise ValueError("缺少逐圈資料或車手名單")
    codes = []
    for driver in payload["drivers"]:
        if not isinstance(driver, dict) or any(not isinstance(driver.get(k), str) or not driver[k].strip() for k in ("code", "name", "team")):
            raise ValueError("逐圈車手名單格式無效")
        codes.append(driver["code"])
    if len(codes) != len(set(codes)):
        raise ValueError("車手代碼重複")
    omitted = payload.get("omitted_rows")
    if type(omitted) is not int or omitted < 0:
        raise ValueError("缺漏筆數無效")
    seen = set()
    for row in payload["laps"]:
        if not isinstance(row, dict) or row.get("driver") not in codes:
            raise ValueError("逐圈資料包含不明車手")
        number = row.get("lap")
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not np.isfinite(number) or number < 1 or not float(number).is_integer():
            raise ValueError("圈次無效")
        key = (row["driver"], number)
        if key in seen:
            raise ValueError("同車手圈次重複")
        seen.add(key)
        for field in (*TIME_FIELDS, *NUMBER_FIELDS):
            if field not in row:
                raise ValueError(f"缺少欄位：{field}")
            value = row[field]
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
                raise ValueError(f"{field} 數值無效")
            if field in ("lap_seconds", "sector1_seconds", "sector2_seconds", "sector3_seconds", "stint", "position") and value <= 0:
                raise ValueError(f"{field} 必須大於零")
            if field in ("stint", "position") and not float(value).is_integer():
                raise ValueError(f"{field} 必須為整數")
        for field in BOOL_FIELDS:
            if field not in row or (row[field] is not None and type(row[field]) is not bool):
                raise ValueError(f"{field} 旗標無效")
        for field in ("compound", "track_status"):
            if field not in row or (row[field] is not None and (not isinstance(row[field], str) or not row[field])):
                raise ValueError(f"{field} 格式無效")
        if row["start_seconds"] is not None and row["end_seconds"] is not None and row["end_seconds"] < row["start_seconds"]:
            raise ValueError("圈末時間早於圈初")
    frame = pd.DataFrame(payload["laps"]).sort_values(["driver", "lap"]).reset_index(drop=True)
    return payload, frame


def read_laps(path, expected):
    return validate_laps(json.loads(Path(path).read_text(encoding="utf-8")), expected)


def exclusion_reason(row):
    reasons = []
    if pd.isna(row["lap_seconds"]): reasons.append("無圈速")
    if row["lap"] == 1: reasons.append("起跑圈")
    if pd.notna(row["pit_in_seconds"]) or pd.notna(row["pit_out_seconds"]): reasons.append("進出站圈")
    if row["track_status"] != "1": reasons.append("非全圈綠旗或狀態缺漏")
    if row["accurate"] is not True: reasons.append("計時未確認可靠")
    if row["deleted"] is not False: reasons.append("刪圈或刪圈狀態缺漏")
    if row["generated"] is not False: reasons.append("補建圈或補建狀態缺漏")
    return "、".join(reasons)


def pace_rows(frame):
    result = frame.copy()
    result["excluded_reason"] = [exclusion_reason(row) for row in result.to_dict("records")]
    result["included"] = result["excluded_reason"].eq("")
    return result


def stint_summary(frame):
    """Observed laps and median only; no causal tyre-degradation estimate."""
    selected = pace_rows(frame)
    rows = []
    for (driver, stint, compound), group in selected.groupby(["driver", "stint", "compound"], dropna=False):
        clean = group[group["included"]]
        rows.append({"driver": driver, "stint": stint, "compound": compound,
                     "first_lap": int(group["lap"].min()), "last_lap": int(group["lap"].max()),
                     "recorded_laps": len(group), "eligible_laps": len(clean),
                     "median_seconds": None if clean.empty else float(clean["lap_seconds"].median())})
    return pd.DataFrame(rows)
