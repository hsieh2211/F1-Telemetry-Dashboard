from pathlib import Path
import json
import logging
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
from race_pace_ui import render_race_pace
from analysis_theme import PALETTE, style_chart

# Keep the UI session list self-contained so Streamlit hot reloads a newly
# deployed session type even when an older imported race_data module is still
# alive in the worker process.
SESSION_NAMES = {
    "R": "正賽 (Race)",
    "Q": "排位賽 (Qualifying)",
    "S": "衝刺賽 (Sprint)",
}

st.set_page_config(page_title="Fastlap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
if st.session_state.get("page", "home") == "home":
    from homepage import render_home
    render_home(Path(__file__).resolve().parent)
    st.stop()
st.html("<style>" + (Path(__file__).resolve().parent / "analysis.css").read_text(encoding="utf-8") + "</style>")
if st.button("回到 2026 首頁"):
    st.session_state.update(page="home", home_event=st.session_state.get("event_index", 0),
                            home_session=st.session_state.get("session_code", "R"), home_section="案例與分析")
    for source, target in (("analysis_a", "case_a"), ("analysis_b", "case_b")):
        if st.session_state.get(source):
            st.session_state[target] = st.session_state[source]
    st.rerun()
st.html('<div class="fp-analysis-brand"><strong>FASTLAP <span>PRO</span></strong><small>2026 賽季 · 離線數據分析</small></div>')
st.title("賽事數據比對")
context_slot = st.container()
tab1, pace_tab, tab2 = st.tabs(["最快圈比對", "整場節奏與輪胎", "單圈資料"])


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
st.sidebar.header("比較設定")
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
    event_index = st.sidebar.selectbox("1. 選擇分站", range(len(events)), format_func=event_label, key="event_index")
    selected = events[event_index]
    selected_event = selected["event"]
    selected_session_codes = [code for code in SESSION_NAMES if code in selected["sessions"]]
    if st.session_state.get("session_code") not in selected_session_codes:
        st.session_state["session_code"] = selected_session_codes[0]
    selected_type_code = st.sidebar.selectbox(
        "2. 比賽類型", selected_session_codes, format_func=SESSION_NAMES.get, key="session_code"
    )
    start = selected["sessions"][selected_type_code]["start_utc"]
    state, message = session_state(start, now)
    st.sidebar.caption("分站、場次與 A／B 車手會沿用到各個分析分頁。")
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
    with pace_tab:
        st.info("請先選擇已保存且可讀取的場次。")

if ready:
    driver_list = list(drivers)
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
    driver1 = st.sidebar.selectbox("3. 基準車手 (A)", driver_list, format_func=driver_label, key="analysis_a")
    driver2 = st.sidebar.selectbox("4. 對比車手 (B)", driver_list, format_func=driver_label, key="analysis_b")
    with context_slot:
        st.subheader(f"{current_year} · {guide_titles.get(selected_event, {}).get('title', selected_event)} · {SESSION_NAMES[selected_type_code]}")
        st.caption(f"A｜{driver1}　／　B｜{driver2} · 車隊依本場匯出紀錄顯示。")
    st.sidebar.caption(f"完整車手名單 {len(drivers)} 位；其中 {len(available_codes)} 位有可比較的最快圈遙測。")
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
        st.sidebar.warning("部分車手資料未通過檢查")
        with st.sidebar.expander("查看原因"):
            st.write(skipped)
    with tab1, st.container(border=True, key="lap_summary"):
        left, right, gap_column = st.columns(3)
        left.metric(f"A｜{driver1} 最快圈", format_lap(drivers[driver1]["lap_seconds"]))
        right.metric(f"B｜{driver2} 最快圈", format_lap(drivers[driver2]["lap_seconds"]))
        gap = drivers[driver2]["lap_seconds"] - drivers[driver1]["lap_seconds"]
        gap_column.metric("兩個最快圈用時差", f"{abs(gap):.3f} 秒", delta=None)
        st.caption("依匯出精度兩圈用時相同。" if abs(gap) < .0005 else f"{driver1 if gap > 0 else driver2} 的這個最快圈用時較少；這不是完賽差距。")
        notes = comparison_flags(drivers[driver1], drivers[driver2])
        if notes:
            st.caption("比較條件｜" + "　".join(notes))
        st.caption("個人最快圈比較，不能代表整場比賽節奏。")
    ref_tel = drivers[driver1]["telemetry"].copy()
    comp_tel = drivers[driver2]["telemetry"].copy()
    delta_time = comparison_delta(ref_tel, comp_tel)

    with tab1:
        try:
            plt.style.use('dark_background')
            # 視覺化架構：建立四層聯動畫布
            fig, (ax_s, ax_d, ax_t, ax_b) = plt.subplots(4, 1, figsize=(12, 9), height_ratios=[3, 2, 1.5, 1], sharex=True)
    
            # [Layer 1] 時速對比層 (Speed)
            ax_s.set_title(f"{current_year} {selected_event}: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
            ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color=PALETTE[0], label=f"{driver1} (Base)")
            ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color=PALETTE[1], linestyle='--', label=f"{driver2} (Comp)")
            ax_s.set_ylabel('Speed (km/h)')
            ax_s.legend(loc='lower right')
            ax_s.grid(True, linestyle=':', alpha=0.3)
    
            # [Layer 2] Delta Time (時間差)
            ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
            ax_d.axhline(0, color='grey', linestyle='--')
            ax_d.set_ylabel(f"Delta (s)\n(+) {driver1} Faster\n(-) {driver2} Faster")
            ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='green', alpha=0.3)
            ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='red', alpha=0.3)
            ax_d.grid(True, linestyle=':', alpha=0.3)
    
            # [Layer 3] 油門訊號
            ax_t.plot(ref_tel['Distance'], ref_tel['Throttle'], color=PALETTE[0], alpha=0.8)
            ax_t.plot(comp_tel['Distance'], comp_tel['Throttle'], color=PALETTE[1], linestyle='--', alpha=0.8)
            ax_t.set_ylabel('Throttle (%)')
            ax_t.axhline(100, color='grey', linestyle=':', alpha=0.5)
            ax_t.grid(True, linestyle=':', alpha=0.3)
    
            # [Layer 4] 煞車層 (Brake)
            ax_b.step(ref_tel['Distance'], ref_tel['Brake'], color=PALETTE[0], where='post')
            ax_b.step(comp_tel['Distance'], comp_tel['Brake'], color=PALETTE[1], linestyle='--', where='post')
            ax_b.set_yticks([0, 1])
            ax_t.set_ylim(-5, 105)
            ax_b.set_ylabel('Brake')
            ax_b.set_xlabel('Distance (m)')
            ax_b.grid(True, linestyle=':', alpha=0.3)
    
            style_chart(fig, (ax_s, ax_d, ax_t, ax_b))
            fig.tight_layout(pad=1.3)
            st.pyplot(fig, width='stretch')
            plt.close(fig)
    
            st.caption("時間差為依各圈相對行駛進度對齊的近似值，不是官方分段計時或比賽即時差距。正值表示基準車手在對齊位置用時較少。")
            st.caption("油門與煞車保留匯出數值；僅憑這些訊號不能直接判定電池回充或動力分配。")
    # ==========================================
            # 🌟 視覺大絕招：2D 賽道路線與配速熱力圖
            # ==========================================
            st.markdown("### 🗺️ 賽道路線與配速熱力圖 (Track Speed Map)")
            
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
            cbar.set_label('Speed (km/h)', fontsize=12)
    
            ax_track.set_title(f"{current_year} {selected_event} - {driver1} Track Speed Map", fontsize=14, pad=15)
    
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

