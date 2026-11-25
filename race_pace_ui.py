"""Offline race pace, observed tyre usage and pit-entry records."""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from race_pace import laps_path, read_laps, pace_rows, stint_summary
from race_guide import start_label
from season_profiles import load_profiles

TYRES = {"SOFT": ("軟胎", "#ff605b"), "MEDIUM": ("中性胎", "#ffd447"),
         "HARD": ("硬胎", "#e5e7eb"), "INTERMEDIATE": ("半雨胎", "#55c985"), "WET": ("全雨胎", "#5da5ff")}


def render_race_pace(root, identity, title):
    year, event, session = identity
    st.subheader(f"{title} · 整場節奏與輪胎使用")
    path = laps_path(root, *identity)
    if not path.is_file():
        st.info("此場次尚未收錄逐圈資料；目前的最快圈資料仍可正常比較。")
        return
    try:
        payload, frame = read_laps(path, identity)
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error(f"逐圈資料未通過檢查：{error}")
        return
    roster = {d["code"]: d for d in payload["drivers"]}
    try:
        profiles = load_profiles(root, year)["drivers"]
    except (OSError, ValueError, KeyError, TypeError):
        profiles = {}
    available = [code for code in roster if code in set(frame["driver"])]
    chosen = st.multiselect("比較車手（最多 4 位）", available,
                            default=available[:2], max_selections=4,
                            format_func=lambda c: f"{c} · {profiles.get(c, {}).get('name_zh') or roster[c]['name']}",
                            key=f"pace_drivers_{year}_{event}_{session}")
    st.caption(f"離線資料：{len(roster)} 位名單、{len(frame)} 筆逐圈紀錄；匯出時間 {start_label(payload['exported_at'])}（台灣時間）。")
    if payload["omitted_rows"]:
        st.warning(f"另有 {payload['omitted_rows']} 筆資料缺少車手或圈次，無法定位，未納入圖表。")
    missing = [code for code in roster if code not in set(frame["driver"])]
    if missing:
        st.caption("沒有逐圈紀錄的車手：" + "、".join(missing))
    if not chosen:
        st.info("請至少選擇一位車手。")
        return
    selected = frame[frame["driver"].isin(chosen)]
    lower, upper = int(selected["lap"].min()), int(selected["lap"].max())
    if upper > lower:
        interval = st.slider("比較圈次範圍", lower, upper, (lower, upper), key=f"pace_range_{year}_{event}_{session}")
        selected = selected[selected["lap"].between(*interval)]
        lower, upper = interval
    annotated = pace_rows(selected)
    clean = annotated[annotated["included"]]
    st.caption("預設節奏僅採全圈綠旗、計時可靠、確認未刪除且非補建的圈；排除起跑圈與進出站圈。原始紀錄保留在下方表格。")
    columns = st.columns(len(chosen))
    for column, driver in zip(columns, chosen):
        group = clean[clean["driver"] == driver]
        column.metric(f"{driver} 有效圈中位數", "資料不足" if group.empty else f"{group['lap_seconds'].median():.3f} 秒")
        total = int((annotated["driver"] == driver).sum())
        column.caption(f"採用 {len(group)} / {total} 圈")
    with plt.style.context("dark_background"):
        fig, axis = plt.subplots(figsize=(11, 4))
        for driver in chosen:
            # Leave NaN gaps across excluded laps instead of implying continuity.
            group = annotated[annotated["driver"] == driver].set_index("lap").reindex(range(lower, upper + 1))
            series = group["lap_seconds"].where(group["included"].eq(True))
            axis.plot(group.index, series, marker=".", label=driver)
        axis.set(xlabel="Race lap", ylabel="Lap time (s)")
        axis.grid(alpha=.2)
        axis.legend()
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    if clean.empty:
        st.info("所選範圍沒有符合條件的圈；請查看排除原因或改選圈次。")
    st.caption("中位數未校正油量、交通、天候與輪胎條件；不能直接當作車手實力排名或純輪胎衰退率。")
    st.subheader("輪胎使用紀錄")
    st.caption("每個點代表一筆有胎種的圈次紀錄；缺少胎種以灰色表示。顏色變化不等於已確認換胎，須搭配 stint 與進出站紀錄。")
    with plt.style.context("dark_background"):
        fig, axis = plt.subplots(figsize=(11, max(2, len(chosen) * .6)))
        for y, driver in enumerate(chosen):
            group = selected[selected["driver"] == driver]
            for compound, rows in group.groupby("compound", dropna=False):
                name, color = TYRES.get(compound, ("未提供", "#888888"))
                axis.scatter(rows["lap"], [y] * len(rows), marker="s", s=60, color=color)
        axis.set_yticks(range(len(chosen)), chosen)
        axis.set_xlabel("Race lap")
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    st.caption("／".join(f"{name}：{code}" for code, (name, _) in TYRES.items()))
    summary = stint_summary(selected).rename(columns={"driver": "車手", "stint": "Stint", "compound": "胎種",
        "first_lap": "首筆圈次", "last_lap": "末筆圈次", "recorded_laps": "紀錄圈數",
        "eligible_laps": "採用圈數", "median_seconds": "有效圈中位數（秒）"})
    st.dataframe(summary, hide_index=True, width="stretch")
    st.subheader("進出站紀錄")
    pits = selected[selected["pit_in_seconds"].notna() | selected["pit_out_seconds"].notna()]
    if pits.empty:
        st.info("所選範圍沒有進出站時間紀錄；這不代表已確認沒有進站。")
    else:
        st.dataframe(pits[["driver", "lap", "pit_in_seconds", "pit_out_seconds", "stint", "compound"]].rename(columns={
            "driver": "車手", "lap": "圈次", "pit_in_seconds": "進入維修區（場次秒）",
            "pit_out_seconds": "離開維修區（場次秒）", "stint": "Stint", "compound": "胎種"}), hide_index=True, width="stretch")
    st.caption("時間是從場次計時原點起算；進出站可能跨圈。此表不推算停車換胎秒數、進站損失或策略成敗。")
    with st.expander("逐圈原始值與排除原因"):
        st.dataframe(annotated.rename(columns={"driver": "車手", "lap": "圈次", "lap_seconds": "圈速（秒）",
            "included": "納入節奏", "excluded_reason": "排除原因"}), hide_index=True, width="stretch")
        st.download_button("下載所選逐圈 CSV", annotated.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{year}_{session}_selected_laps.csv", mime="text/csv")
