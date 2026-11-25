"""Offline race pace with shared A/B selection and compact analysis panels."""
import pandas as pd
import streamlit as st

from analysis_theme import PALETTE
from analysis_charts import pace_charts, tyre_chart
from race_pace import laps_path, read_laps, pace_rows, stint_summary
from race_guide import start_label
from season_profiles import load_profiles

TYRES = {"SOFT": ("軟胎", "#ff605b"), "MEDIUM": ("中性胎", "#ffd447"),
         "HARD": ("硬胎", "#e5e7eb"), "INTERMEDIATE": ("半雨胎", "#55c985"), "WET": ("全雨胎", "#5da5ff")}


def render_race_pace(root, identity, title, selected_drivers=None):
    year, event, session = identity
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
    def label(code):
        return f"{code} · {profiles.get(code, {}).get('name_zh') or roster[code]['name']}"
    st.subheader("逐圈節奏")
    if selected_drivers is None:
        chosen = st.multiselect("比較車手（最多 4 位）", available, default=available[:2],
                                max_selections=4, format_func=label,
                                key=f"pace_drivers_{year}_{event}_{session}")
        colour_order = chosen
    else:
        base = list(dict.fromkeys(selected_drivers))
        missing_selected = [c for c in base if c not in available]
        if missing_selected:
            st.info("、".join(missing_selected) + " 沒有逐圈紀錄，未納入節奏圖。")
        options = [c for c in available if c not in base]
        key = f"pace_extra_{year}_{event}_{session}"
        if key in st.session_state:
            st.session_state[key] = [c for c in st.session_state[key] if c in options]
        with st.expander("加入其他車手（選填，最多 2 位）"):
            extra = st.multiselect("額外比較車手", options, max_selections=2, format_func=label, key=key)
        chosen = [c for c in base if c in available] + extra
        colour_order = base + extra
    colours = {code: PALETTE[i % len(PALETTE)] for i, code in enumerate(colour_order)}
    st.caption("比較｜" + " ／ ".join(chosen) + f"　·　已收錄 {len(frame)} 筆逐圈紀錄")
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
    with st.container(border=True, key="pace_summary"):
        # Two columns per row stay readable for four-driver comparisons.
        for start in range(0, len(chosen), 2):
            for column, driver in zip(st.columns(min(2, len(chosen) - start)), chosen[start:start + 2]):
                group = clean[clean["driver"] == driver]
                column.metric(f"{driver} 有效圈中位數", "資料不足" if group.empty else f"{group['lap_seconds'].median():.3f} 秒")
                total = int((annotated["driver"] == driver).sum())
                column.caption(f"採用 {len(group)} / {total} 圈")
    curve, exclusions = pace_charts(annotated, chosen, colours, lower, upper)
    st.altair_chart(curve, width="stretch", theme=None)
    st.altair_chart(exclusions, width="stretch", theme=None)
    st.caption("下方 × 為未納入節奏的圈，點選或懸停可查原因。中位數未校正油量、交通、天候與輪胎條件。")
    if clean.empty:
        st.info("所選範圍沒有符合條件的圈；請查看排除原因或改選圈次。")
    st.subheader("輪胎使用")
    st.altair_chart(tyre_chart(selected, chosen, TYRES, lower, upper), width="stretch", theme=None)
    st.caption("每格是一圈的胎種紀錄；顏色改變須搭配輪胎段與進出站紀錄判讀，不直接代表衰退或策略優劣。")
    with st.expander("輪胎段明細"):
        summary = stint_summary(selected).rename(columns={"driver": "車手", "stint": "輪胎段（Stint）", "compound": "胎種",
            "first_lap": "首筆圈次", "last_lap": "末筆圈次", "recorded_laps": "紀錄圈數",
            "eligible_laps": "採用圈數", "median_seconds": "有效圈中位數（秒）"})
        st.dataframe(summary.round(3), hide_index=True, width="stretch")
    pits = selected[selected["pit_in_seconds"].notna() | selected["pit_out_seconds"].notna()]
    with st.expander(f"進出站紀錄 · {len(pits)} 筆"):
        if pits.empty:
            st.info("所選範圍沒有進出站時間紀錄；這不代表已確認沒有進站。")
        else:
            st.dataframe(pits[["driver", "lap", "pit_in_seconds", "pit_out_seconds", "stint", "compound"]].rename(columns={
                "driver": "車手", "lap": "圈次", "pit_in_seconds": "進入維修區（場次秒）",
                "pit_out_seconds": "離開維修區（場次秒）", "stint": "輪胎段", "compound": "胎種"}), hide_index=True, width="stretch")
        st.caption("時間從場次計時原點起算，進出站可能跨圈；不等於停車換胎秒數或進站損失。")
    with st.expander("逐圈原始值與排除原因"):
        st.caption("保留所有所選圈次；起跑、進出站、非全圈綠旗、計時不可靠、刪圈、補建圈及品質旗標缺漏不納入節奏。")
        st.dataframe(annotated.rename(columns={"driver": "車手", "lap": "圈次", "lap_seconds": "圈速（秒）",
            "included": "納入節奏", "excluded_reason": "排除原因", "stint": "輪胎段", "compound": "胎種",
            "tyre_life": "胎齡", "accurate": "計時可靠", "deleted": "已刪圈", "generated": "補建圈",
            "track_status": "賽道狀態", "position": "順位", "fresh_tyre": "新胎",
            "start_seconds": "圈初（場次秒）", "end_seconds": "圈末（場次秒）",
            "pit_in_seconds": "進站（場次秒）", "pit_out_seconds": "出站（場次秒）",
            "sector1_seconds": "第一段（秒）", "sector2_seconds": "第二段（秒）", "sector3_seconds": "第三段（秒）"}), hide_index=True, width="stretch")
        st.download_button("下載所選逐圈 CSV", annotated.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{year}_{session}_selected_laps.csv", mime="text/csv")
    with st.expander("資料來源與缺漏"):
        st.caption(f"{title} · {year} · {session}｜FastF1 離線匯出")
        st.caption(f"{len(roster)} 位名單、{len(frame)} 筆紀錄；匯出時間 {start_label(payload['exported_at'])}（台灣時間）。")
        if payload["omitted_rows"]:
            st.warning(f"另有 {payload['omitted_rows']} 筆資料缺少車手或圈次，無法定位，未納入圖表。")
        missing = [code for code in roster if code not in set(frame["driver"])]
        if missing:
            st.caption("沒有逐圈紀錄的車手：" + "、".join(missing))
