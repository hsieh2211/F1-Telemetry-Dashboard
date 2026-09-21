"""Run on your own computer: py export_data.py --year 2026

Downloads sequentially, resumes validated exports, and never publishes an
unfinished session. The website itself makes no FastF1 requests.
"""
import argparse
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from race_data import (UTC, COLUMNS, SESSION_NAMES, read_catalogue, read_payload,
                       validate_payload, existing_path, data_path, session_state)

ROOT = Path(__file__).resolve().parent
MAX_TELEMETRY_POINTS = 300


def compact_telemetry(frame, max_points=MAX_TELEMETRY_POINTS):
    """Keep web payloads small while preserving lap endpoints and shape."""
    if len(frame) <= max_points:
        return frame.reset_index(drop=True)
    indices = np.linspace(0, len(frame) - 1, max_points, dtype=int)
    return frame.iloc[np.unique(indices)].reset_index(drop=True)


def atomic_json(path, payload):
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as output:
            name = output.name
            output.write(text)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def refresh_catalogue(fastf1, year, path):
    import pandas as pd
    schedule = fastf1.get_event_schedule(year, include_testing=False, backend="fastf1")
    events = []
    for _, row in schedule.iterrows():
        sessions = {}
        for code, name in (("R", "Race"), ("Q", "Qualifying"), ("S", "Sprint")):
            start = None
            for number in range(1, 6):
                if row[f"Session{number}"] == name:
                    value = row[f"Session{number}DateUtc"]
                    if pd.notna(value):
                        stamp = pd.Timestamp(value)
                        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
                        start = stamp.isoformat()
            if code in ("R", "Q") or start is not None:
                sessions[code] = {"start_utc": start}
        events.append({"round": int(row["RoundNumber"]), "event": row["EventName"], "sessions": sessions})
    if not events:
        raise ValueError("賽程為空；保留舊賽程，不覆寫")
    payload = {"year": year, "updated_at": datetime.now(UTC).isoformat(),
               "source": "FastF1 get_event_schedule / fastf1 backend", "events": events}
    atomic_json(path, payload)
    return read_catalogue(path)


def export_session(fastf1, year, event, code):
    session = fastf1.get_session(year, event, code)
    session.load(laps=True, telemetry=True, weather=False, messages=True)
    # Qualifying has multiple Finished markers; only Finalised confirms the end.
    statuses = session.session_status["Status"].astype(str)
    if "Finalised" not in set(statuses):
        raise ValueError("尚未確認場次結束（缺少 Finalised），稍後再試")
    if session.laps.empty:
        raise ValueError("圈速資料為空")
    drivers, skipped = [], []
    for _, row in session.results.iterrows():
        driver_code = row["Abbreviation"]
        driver = {"code": str(driver_code), "name": str(row["FullName"]),
                  "team": str(row["TeamName"])}
        try:
            driver_laps = session.laps.pick_drivers(driver_code)
            lap = driver_laps.pick_fastest()
            if lap is None:
                lap = driver_laps.pick_fastest(only_by_time=True)
            if lap is None:
                raise ValueError("沒有有效最快圈")
            frame = lap.get_telemetry().add_distance()[COLUMNS].copy()
            frame["Time"] = frame["Time"].dt.total_seconds()
            frame = compact_telemetry(frame)
            tyre_life = float(lap["TyreLife"])
            if not np.isfinite(tyre_life) or tyre_life <= 0:
                tyre_life = None
            driver.update({"available": True,
                           "lap_seconds": lap["LapTime"].total_seconds(),
                           "lap_number": int(lap["LapNumber"]),
                           "compound": str(lap["Compound"]),
                           "tyre_life": tyre_life,
                           "telemetry": json.loads(frame.to_json(orient="records"))})
        except Exception as error:
            reason = str(error)
            driver.update({"available": False, "reason": reason})
            skipped.append(f"{driver_code}: {reason}")
        drivers.append(driver)
    payload = {"year": year, "event": event, "session": code, "drivers": drivers,
               "exported_at": datetime.now(UTC).isoformat(), "source": "FastF1",
               "fastf1_version": fastf1.__version__, "session_finalised": True}
    _, _, _, valid, invalid = validate_payload(payload, (year, event, code))
    invalid_reasons = {}
    for item in invalid:
        invalid_code, separator, reason = item.partition("：")
        if separator:
            invalid_reasons[invalid_code] = reason
    normalized = []
    for driver in drivers:
        if driver["code"] in valid:
            normalized.append(driver)
        else:
            normalized.append({"code": driver["code"], "name": driver["name"],
                               "team": driver["team"], "available": False,
                               "reason": invalid_reasons.get(driver["code"], "遙測資料未通過檢查")})
    payload["drivers"] = normalized
    payload["skipped_drivers"] = skipped + invalid
    validate_payload(payload, (year, event, code))
    return payload


def run(args, fastf1, root=ROOT):
    cache = root / "f1_cache_v99"
    cache.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))
    catalogue_path = root / "data" / f"schedule_{args.year}.json"
    # Refresh normally; explicit --saved-schedule allows a reproducible offline
    # schedule snapshot when refreshing is unavailable (does not bypass access).
    catalogue = (read_catalogue(catalogue_path) if args.saved_schedule else
                 refresh_catalogue(fastf1, args.year, catalogue_path))
    if catalogue["year"] != args.year:
        raise ValueError("賽程年份不符")
    entries, failures = [], 0
    now = datetime.now(UTC)
    report_path = root / "data" / f"export_report_{args.year}.json"
    tried = False
    for event in catalogue["events"]:
        if args.event and event["event"] != args.event:
            continue
        for code in args.sessions:
            if code not in event["sessions"]:
                continue
            record = {"event": event["event"], "session": code}
            state, message = session_state(event["sessions"][code]["start_utc"], now)
            path = existing_path(root, args.year, event["event"], code)
            if state in ("future", "unknown", "waiting"):
                record.update(status=state, detail=message)
            elif failures >= 3:
                record.update(status="not_attempted", detail="連續三場失敗，停止下載，請檢查連線或資料源")
            else:
                valid_saved = False
                try:
                    read_payload(path, (args.year, event["event"], code))
                    valid_saved = True
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                if valid_saved and not args.refresh:
                    record.update(status="saved", detail="已存在有效資料，略過下載")
                    failures = 0
                else:
                    if tried:
                        time.sleep(3)
                    tried = True
                    try:
                        payload = export_session(fastf1, args.year, event["event"], code)
                        destination = data_path(root, args.year, event["event"], code)
                        atomic_json(destination, payload)
                        failures = 0
                        record.update(status="exported", drivers=len(payload["drivers"]),
                                      skipped=payload["skipped_drivers"], detail=str(destination.relative_to(root)))
                    except Exception as error:
                        failures += 1
                        record.update(status="failed", detail=str(error), preserved_existing=valid_saved)
            entries.append(record)
            print(f'{record["event"]} / {code}: {record["status"]} — {record["detail"]}', flush=True)
            atomic_json(report_path, {"year": args.year, "checked_at": now.isoformat(), "sessions": entries})
    if not entries:
        raise ValueError("沒有符合的場次，請確認 --event 完整英文名稱")
    incomplete = sum(e["status"] in ("failed", "not_attempted") for e in entries)
    available = sum(e["status"] in ("saved", "exported") for e in entries)
    print(f"\n完成：可用 {available} 場；失敗或未嘗試 {incomplete} 場。")
    print("請上傳 data 資料夾（不要上傳 f1_cache_v99）。網站不會自動收到你電腦上的檔案。")
    print(f"逐場結果：{report_path}")
    return 1 if incomplete else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--event", help="只處理指定分站的完整英文名稱")
    parser.add_argument("--sessions", nargs="+", choices=SESSION_NAMES, default=["R", "Q"])
    parser.add_argument("--refresh", action="store_true", help="重新匯出已保存資料；失敗時保留舊檔")
    parser.add_argument("--saved-schedule", action="store_true", help="使用已保存賽程，不更新賽程")
    args = parser.parse_args()
    import fastf1
    try:
        return run(args, fastf1)
    except Exception as error:
        print(f"停止：{error}。未完成的資料不會標示為成功。", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
