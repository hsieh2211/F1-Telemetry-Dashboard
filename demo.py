from pathlib import Path
import json
import logging
from html import escape
from datetime import datetime, timezone
from race_data import read_catalogue, existing_path, read_payload, session_state, SESSION_NAMES

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.collections as mcoll
from season_content import comparison_flags
from season_profiles import load_profiles, known
from race_guide import start_label
from analysis_theme import PALETTE, style_chart
from analysis_telemetry import telemetry_chart, aligned_samples
from analysis_window import distance_controls, set_window, window_observation
# Long-lived Streamlit workers can retain imported UI modules after a deploy.
# Refresh this release's UI modules once, before constructing any widgets.
import importlib
for module_name in ("site_navigation", "homepage", "site_sections", "race_lap_workbench", "race_pace_ui"):
    ui_module = importlib.import_module(module_name)
    if getattr(ui_module, "_fp_ui_release", None) != "2026-11-27-linked-laps-2":
        importlib.reload(ui_module)
        ui_module._fp_ui_release = "2026-11-27-linked-laps-2"
from site_navigation import render_navigation, share_current, go_to
from race_pace_ui import render_race_pace

# Keep the UI session list self-contained so Streamlit hot reloads a newly
# deployed session type even when an older imported race_data module is still
# alive in the worker process.
SESSION_NAMES = {
    "R": "正賽 (Race)",
    "Q": "排位賽 (Qualifying)",
    "S": "衝刺賽 (Sprint)",
}

st.set_page_config(page_title="Fastlap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
site_root = Path(__file__).resolve().parent
st.html("<style>" + (site_root / "site_navigation.css").read_text(encoding="utf-8") + "</style>")
page = render_navigation(site_root)
if page == "home":
    from homepage import render_home
    render_home(site_root)
    share_current(site_root)
    st.stop()
if page in ("calendar", "learn"):
    from site_sections import render_calendar, render_learning
    try:
        (render_calendar if page == "calendar" else render_learning)(site_root)
        share_current(site_root)
    except (OSError, ValueError, TypeError, KeyError) as error:
        st.error(f"2026 內容暫時無法讀取：{error}")
    st.stop()
st.html("<style>" + (Path(__file__).resolve().parent / "analysis.css").read_text(encoding="utf-8") + "</style>")
nav = st.container(key="analysis_nav")
brand, back = nav.columns([5, 1.4])
back.button("回到首頁", on_click=go_to, args=("觀賽首頁",))
brand.html('<div class="fp-analysis-brand"><strong>FASTLAP <span>PRO</span></strong><h1>賽事分析</h1><small>2026 賽季</small></div>')
settings_slot = st.container(key="analysis_settings")
context_slot = st.container()
share_slot = st.container()
tab1, pace_tab, tab2 = st.tabs(["最快圈比對", "整場節奏與輪胎", "單圈資料"], key="analysis_tab", bind="query-params", on_change="rerun")


@st.cache_data(max_entries=4, show_spinner=False)
def load_saved_data(path, version, expected):
    # version changes when the deployed file changes, invalidating the cache.
    return read_payload(path, expected)


def comparison_delta(reference, comparison):
    # Distance is integrated separately for each lap. Align their start/end
    # by lap progress before interpolating; this is an approximate comparison.
    ref_distance = reference["Distance"].to_numpy()
    comp_distance = comparison["Distance"].to_numpy()
    ref_progress = (ref_distance - ref_distance[0]) / (ref_distance[-1] - ref_distance[0])
    comp_progress = (comp_distance - comp_distance[0]) / (comp_distance[-1] - comp_distance[0])
    delta = np.interp(ref_progress, comp_progress, comparison["Time"]) - reference["Time"].to_numpy()
    return delta


def format_lap(seconds):
    milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(milliseconds, 60000)
    return f"{minutes}:{remainder / 1000:06.3f}"


ready = False
root = Path(__file__).resolve().parent
with settings_slot:
    controls = st.expander("比較設定 · 分站／場次／車手", expanded=False)
    event_control, session_control = controls.columns([3, 1])
    large = controls.checkbox("大字閱讀模式", key="analysis_large", help="放大分析頁文字與圖表標籤；不更改資料。")
    if large:
        st.html("<style>html{font-size:18px}</style>")
try:
    catalogue = read_catalogue(root / "data" / "schedule_2026.json")
    current_year = catalogue["year"]
    events = catalogue["events"]
    now = datetime.now(timezone.utc)
    try:
        guide_titles = json.loads((root / "data/race_guides_2026.json").read_text(encoding="utf-8"))["events"]
        profiles = load_profiles(root, current_year)
    except (OSError, ValueError, KeyError, TypeError):
        guide_titles, profiles = {}, {"drivers": {}}
    def event_label(index):
        event = events[index]
        session_codes = [code for code in SESSION_NAMES if code in event["sessions"]]
        available = sum(existing_path(root, current_year, event["event"], code).is_file()
                        for code in session_codes)
        return f'{guide_titles.get(event["event"], {}).get("title", event["event"])} ｜已存 {available}/{len(session_codes)} 場'
    event_index = event_control.selectbox("分站", range(len(events)), format_func=event_label, key="event_index")
    selected = events[event_index]
    selected_event = selected["event"]
    selected_session_codes = [code for code in SESSION_NAMES if code in selected["sessions"]]
    if st.session_state.get("session_code") not in selected_session_codes:
        st.session_state["session_code"] = selected_session_codes[0]
    selected_type_code = session_control.selectbox(
        "場次", selected_session_codes, format_func=SESSION_NAMES.get, key="session_code"
    )
    with context_slot:
        st.html(f'<div class="fp-session-line"><strong>{escape(guide_titles.get(selected_event, {}).get("title", selected_event))}</strong><span>{current_year} · {escape(SESSION_NAMES[selected_type_code])}</span><small>依所選場次的離線資料比較</small></div>')
    start = selected["sessions"][selected_type_code]["start_utc"]
    state, message = session_state(start, now)

    path = existing_path(root, current_year, selected_event, selected_type_code)
    if state in ("future", "unknown"):
        for tab in (tab1, tab2):
            with tab:
                st.info(f"{selected_event} · {SESSION_NAMES[selected_type_code]}：{message}")
                if start:
                    st.caption(f"預定開賽：{start_label(start)}（台灣時間）")
    elif not path.is_file():
        for tab in (tab1, tab2):
            with tab:
                st.info(message + "。")
                st.caption("此場次尚未提供可比較資料，請先選擇其他已保存場次。預定時間已過不代表已確認完賽。")
    else:
        file_info = path.stat()
        current_year, selected_event, selected_type_code, drivers, skipped = load_saved_data(
            str(path), (file_info.st_mtime_ns, file_info.st_size),
            (current_year, selected_event, selected_type_code)
        )
        ready = True
except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
    logging.exception("Failed to load saved race data or schedule")
    with tab1:
        st.error(f"此場次或賽程資料無法讀取：{error}")
        st.info("請切換其他分站或重新匯出；名詞解說可回首頁的「2026 賽季知識」查看。")
    with tab2:
        st.info("有效資料載入後即可查看摘要。")

if not ready:
    with share_slot:
        share_current(site_root)
    with pace_tab:
        st.info("請先選擇已保存且可讀取的場次。")

if ready:
    driver_list = list(drivers)
    if any(st.session_state.get(key) and st.session_state[key] not in driver_list for key in ("analysis_a", "analysis_b")):
        with context_slot:
            st.info("連結中的部分車手不在本場名單，已改用可比較車手。")
    available_codes = [code for code, info in drivers.items() if info["available"]]
    def driver_label(code):
        info = drivers[code]
        name = profiles["drivers"].get(code, {}).get("name_zh") or known(info.get("name"))
        suffix = " — 無有效圈速" if not info["available"] else ""
        return f"{code} · {name}（{known(info.get('team'))}）{suffix}"
    if st.session_state.get("analysis_a") not in driver_list:
        st.session_state["analysis_a"] = available_codes[0]
    if st.session_state.get("analysis_b") not in driver_list:
        st.session_state["analysis_b"] = next(
            code for code in available_codes if code != st.session_state["analysis_a"])
    with controls:
        choose_a, choose_b = st.columns(2)
        driver1 = choose_a.selectbox("A · 基準車手", driver_list, format_func=driver_label, key="analysis_a")
        driver2 = choose_b.selectbox("B · 比較車手", driver_list, format_func=driver_label, key="analysis_b")

    with share_slot:
        share_current(site_root)
    if driver1 == driver2:
        with context_slot:
            st.info("請選擇兩位不同車手，才能比較差異。")
        st.stop()
    with pace_tab:
        if selected_type_code == "Q":
            st.info("整場節奏適用正賽與衝刺賽；排位賽請使用最快圈比較。")
        else:
            render_race_pace(root, (current_year, selected_event, selected_type_code),
                             guide_titles.get(selected_event, {}).get("title", selected_event),
                             selected_drivers=[driver1, driver2])
    unavailable = [code for code in (driver1, driver2) if not drivers[code]["available"]]
    if unavailable:
        for tab in (tab1, tab2):
            with tab:
                for code in unavailable:
                    st.info(f"{code} — {drivers[code]['name']}：{drivers[code]['reason']}，因此無法繪製最快圈比較。")
        st.stop()
    if skipped:
        with context_slot, st.expander("部分車手資料未通過檢查 · 查看原因"):
            st.write(skipped)
    with tab1:

        summary = st.container(key="lap_summary")
        left, right, gap_column = summary.columns([1.2, 1.2, 1])
        tyre_names = {"SOFT":"軟胎", "MEDIUM":"中性胎", "HARD":"硬胎", "INTERMEDIATE":"半雨胎", "WET":"全雨胎"}
        for column, code, role, colour in ((left,driver1,"A",PALETTE[0]),(right,driver2,"B",PALETTE[1])):
            info = drivers[code]
            name = profiles["drivers"].get(code,{}).get("name_zh") or known(info.get("name"))
            with column, st.container(border=True, key=f"driver_card_{role}"):
                st.html(f'<div class="fp-driver-heading" style="--driver-colour:{colour}"><span>{role} · {escape(code)}</span><strong>{escape(name)}</strong><small>{escape(known(info.get("team")))}</small></div>')
                st.metric(f"{role}｜{code} 最快圈", format_lap(info["lap_seconds"]))
                lap = info.get("lap_number")
                life = info.get("tyre_life")
                condition = f"第 {int(lap)} 圈" if lap is not None else "圈次未提供"
                condition += " · " + tyre_names.get(info.get("compound"), "胎種未提供")
                condition += f" · 胎齡 {life:g} 圈" if life is not None else " · 胎齡未提供"
                st.caption(condition)
        gap = drivers[driver2]["lap_seconds"] - drivers[driver1]["lap_seconds"]
        with gap_column, st.container(border=True, key="lap_gap"):
            st.html('<div class="fp-gap-label">這兩圈的差距</div>')
            st.metric("兩個最快圈用時差", f"{abs(gap):.3f} 秒", delta=None)
            st.caption("依匯出精度兩圈用時相同。" if abs(gap) < .0005 else f"{driver1 if gap > 0 else driver2} 這一圈用時較少")
            st.caption("個人最快圈，並非完賽差距。")
        notes = comparison_flags(drivers[driver1], drivers[driver2])
        if notes:
            st.html('<div class="fp-condition-note"><strong>比較前先確認</strong><span>' + escape("　".join(notes).replace("SOFT", "軟胎").replace("MEDIUM", "中性胎").replace("HARD", "硬胎").replace("INTERMEDIATE", "半雨胎").replace("WET", "全雨胎")) + '</span></div>')
        else:
            st.caption("胎種、胎齡與圈次欄位相同，仍不代表油量與賽道條件相同。")
    ref_tel = drivers[driver1]["telemetry"].copy()
    comp_tel = drivers[driver2]["telemetry"].copy()
    delta_time = comparison_delta(ref_tel, comp_tel)

    with tab1:
        try:
            maximum = int(np.ceil(float(ref_tel.Distance.iloc[-1])))
            with st.container(border=True, key="lap_workbench"):
                chart_title, chart_controls, reset_control = st.columns([2, 2.5, 1])
                chart_title.html(f'<div class="fp-chart-heading"><h3>單圈遙測</h3><div class="fp-chart-legend"><span style="color:{PALETTE[0]}">A · {escape(driver1)}</span><span style="color:{PALETTE[1]}">B · {escape(driver2)}</span></div></div>')
                view = chart_controls.radio("訊號顯示", ["重點檢視", "完整訊號", "油門訊號", "煞車訊號"], horizontal=True, key="telemetry_view", label_visibility="collapsed")
                reset_control.button("重設整圈", key="reset_distance", on_click=set_window, args=(maximum,), width="stretch")
                window = distance_controls((current_year, selected_event, selected_type_code, driver1, driver2, file_info.st_mtime_ns), maximum)
                samples = aligned_samples(ref_tel, comp_tel, delta_time)
                observation = window_observation(samples, *window, driver1, driver2)
                if observation is None:
                    st.info("請拉開距離範圍的兩端，選擇有長度的區段。")
                else:
                    st.html('<div class="fp-observation"><strong>區段觀察 · 對齊估計</strong><p>' + escape(observation["text"]) + '</p><small>顏色與正負值只表示兩圈的相對用時；無法單憑這張圖判定差距原因。</small></div>')
                    st.caption(f"速度圖點選或移動游標查值，雙擊清除。時間差正值：{driver1} 用時較少；負值：{driver2} 用時較少。")
                    with st.container(key="telemetry_plot"):
                        st.altair_chart(telemetry_chart(ref_tel, comp_tel, delta_time, driver1, driver2, view, window=window, large=large), width="stretch", theme=None)
            with st.expander("對齊方法與判讀限制"):
                st.write("兩圈依各自相對行駛進度對齊，以 A 車手圈內距離顯示。時間差與 B 車手連續訊號採插值估計；B 煞車取對齊位置之前的樣本，保持 0／1。這不是相同實體座標的精確同步，也不是官方分段或比賽即時差距。")
                st.write("最快圈不能代表整場節奏；未控制油量、交通與賽道條件。油門及煞車訊號不能直接判定電池回充、動力分配或策略優劣。")
            with st.expander("下載兩圈原始遙測 CSV"):
                st.caption("保留各車手原始樣本與原始欄位，不含畫面查值的插值。")
                for code, frame in ((driver1, ref_tel), (driver2, comp_tel)):
                    st.download_button(f"下載 {code} 原始遙測", frame.to_csv(index=False).encode("utf-8-sig"),
                                       file_name=f"{current_year}_{selected_event}_{selected_type_code}_{code}_telemetry.csv", mime="text/csv", key=f"telemetry_csv_{code}")
            # 1. 取得基準車手 (ref_tel) 的 X, Y 座標與速度數據
            # 從已驗證的 JSON 遙測讀取座標
            raw_tel = ref_tel
            x = raw_tel['X'].values
            y = raw_tel['Y'].values
            speed = raw_tel['Speed'].values
    
            # 2. 將散落的座標點轉換為連續的線段陣列 (Line segments)
            points = np.array([x, y]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
            # 3. 建立熱力圖顏色映射 (速度越快顏色越亮，使用 'plasma' 漸層)
            norm = plt.Normalize(speed.min(), speed.max())
            lc = mcoll.LineCollection(segments, cmap='plasma', norm=norm, linewidth=6)
            lc.set_array((speed[:-1] + speed[1:]) / 2)
    
            # 4. 建立 2D 賽動畫布
            fig_track, ax_track = plt.subplots(figsize=(10, 6))
            
            # 將彩色賽道加入畫布
            ax_track.add_collection(lc)
            
            # 🔥 關鍵：確保賽道 X 與 Y 比例 1:1 絕對不變形，並隱藏雜亂的座標軸
            ax_track.axis('equal')
            ax_track.axis('off')
    
            # 5. 加入側邊顏色條 (Colorbar) 標示速度數值
            cbar = fig_track.colorbar(lc, ax=ax_track, pad=0.02)
            cbar.set_label('km/h', fontsize=12)
    
            ax_track.set_title(f"{current_year} · {driver1}", fontsize=14, pad=15)
    
            style_chart(fig_track, (ax_track,))
            with st.expander(f"查看 {driver1} 的賽道路線配速圖"):
                st.pyplot(fig_track)
            plt.close(fig_track)
            
        except Exception as e:
            logging.exception('Failed to render saved telemetry')
            st.error(f'圖表無法顯示：{e}')
    
            
    

    with tab2:
        st.subheader("所選兩圈的資料")
        for column, code in zip(st.columns(2), [driver1, driver2]):
            info = drivers[code]
            column.markdown(f"**{driver_label(code)}**")
            column.write(info["team"])
            column.metric("最快圈", format_lap(info["lap_seconds"]))
            lap_number = info["lap_number"]
            if lap_number is None:
                column.write("最快圈圈次：未提供")
            else:
                column.write(f"最快圈圈次：第 {lap_number} 圈")
            column.write("輪胎：" + {"SOFT": "軟胎（SOFT）", "MEDIUM": "中性胎（MEDIUM）", "HARD": "硬胎（HARD）", "INTERMEDIATE": "半雨胎（INTERMEDIATE）", "WET": "全雨胎（WET）"}.get(info["compound"], known(info["compound"])))
            tyre_life = info["tyre_life"]
            if tyre_life is None:
                column.write("最快圈胎齡：未提供")
            else:
                displayed_life = int(tyre_life) if tyre_life.is_integer() else round(tyre_life, 1)
                column.write(f"最快圈胎齡：{displayed_life} 圈")
        st.caption("圈次是該車手跑出最快圈時的比賽圈數；胎齡是當時該套輪胎的使用圈數。舊資料未包含時會標示未提供。")

