"""Load season-labelled editorial content without falling back to another year."""
import json


def load_season_content(root, year, resource):
    if not isinstance(year, int) or resource not in {"learning", "race_guides"}:
        raise ValueError("賽季或內容類型無效")
    data = json.loads((root / "data" / f"{resource}_{year}.json").read_text(encoding="utf-8"))
    if data.get("year") != year:
        raise ValueError("內容年份與所選賽季不一致")
    return data


def comparison_flags(a, b):
    notes = []
    for key, label in (("compound", "胎種"), ("tyre_life", "胎齡"), ("lap_number", "最快圈圈次")):
        left, right = a.get(key), b.get(key)
        if left in (None, "", "未知") or right in (None, "", "未知"):
            notes.append(f"{label}缺資料，無法確認比較條件。")
        elif left != right:
            notes.append(f"{label}不同：{left} ／ {right}。")
    return notes


def window_samples(samples, window):
    if window == "整圈":
        return samples.copy()
    index = {"前 1/3": 0, "中 1/3": 1, "後 1/3": 2}[window]
    low, high = float(samples.Distance.min()), float(samples.Distance.max())
    step = (high - low) / 3
    return samples.loc[samples.Distance.between(low + index * step, low + (index + 1) * step)].copy()

