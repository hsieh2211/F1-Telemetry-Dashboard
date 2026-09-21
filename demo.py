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
import streamlit.components.v1 as components

st.set_page_config(page_title="Fastlap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
st.title("🏁 Fastlap Pro：F1 賽道戰術數據儀表板")
st.caption("已保存賽事資料｜正賽／排位賽最快圈比較；尚未開賽或尚未匯出的場次會顯示提示。")
tab1, tab2, tab3 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)", "📖 互動式教學百科 (Guide)"])


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
st.sidebar.header("⚙️ 戰術控制中心")
try:
    catalogue = read_catalogue(root / "data" / "schedule_2026.json")
    current_year = catalogue["year"]
    events = catalogue["events"]
    now = datetime.now(timezone.utc)
    def event_label(index):
        event = events[index]
        available = sum(existing_path(root, current_year, event["event"], c).is_file()
                        for c in SESSION_NAMES)
        return f'{event["event"]} ｜已存 {available}/2 場'
    event_index = st.sidebar.selectbox("1. 選擇分站", range(len(events)), format_func=event_label)
    selected = events[event_index]
    selected_event = selected["event"]
    selected_type_code = st.sidebar.selectbox(
        "2. 比賽類型", list(SESSION_NAMES), format_func=SESSION_NAMES.get
    )
    start = selected["sessions"][selected_type_code]["start_utc"]
    state, message = session_state(start, now)
    st.sidebar.caption(f'賽程更新：{catalogue.get("updated_at", "未知")[:10]}；時間以 UTC 計算。')
    st.sidebar.caption("資料需先在本機匯出並上傳；網站不會自動下載新場次。")
    path = existing_path(root, current_year, selected_event, selected_type_code)
    if state in ("future", "unknown"):
        for tab in (tab1, tab2):
            with tab:
                st.info(f"{selected_event} · {SESSION_NAMES[selected_type_code]}：{message}")
                if start:
                    st.caption(f"預定開賽：{start}（UTC）")
    elif not path.is_file():
        for tab in (tab1, tab2):
            with tab:
                st.info(message + "。")
                st.caption("賽程時間不等於完賽證明。若已完賽，請執行批次匯出並上傳 data 資料夾；資料源延遲或取消的場次可能沒有遙測。")
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
        st.info("請切換其他分站，或重新匯出此場次；教學百科仍可使用。")
    with tab2:
        st.info("有效資料載入後即可查看摘要。")

if ready:
    driver_list = list(drivers)
    available_codes = [code for code, info in drivers.items() if info["available"]]
    driver_map = {
        code: f"{info['name']} ({info['team']})" + (" — 無有效圈速" if not info["available"] else "")
        for code, info in drivers.items()
    }
    driver1 = st.sidebar.selectbox(
        "3. 基準車手 (A)", driver_list, index=driver_list.index(available_codes[0]),
        format_func=lambda code: f"{code} - {driver_map[code]}"
    )
    driver2 = st.sidebar.selectbox(
        "4. 對比車手 (B)", driver_list, index=driver_list.index(available_codes[1]),
        format_func=lambda code: f"{code} - {driver_map[code]}"
    )
    st.sidebar.caption(f"完整車手名單 {len(drivers)} 位；其中 {len(available_codes)} 位有可比較的最快圈遙測。")
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
    ref_tel = drivers[driver1]["telemetry"].copy()
    comp_tel = drivers[driver2]["telemetry"].copy()
    delta_time = comparison_delta(ref_tel, comp_tel)

    with tab1:
        try:
            plt.style.use('dark_background')
            # 視覺化架構：建立四層聯動畫布
            fig, (ax_s, ax_d, ax_t, ax_b) = plt.subplots(4, 1, figsize=(12, 12), height_ratios=[3, 2, 1.5, 1], sharex=True)
    
            # [Layer 1] 時速對比層 (Speed)
            ax_s.set_title(f"{current_year} {selected_event}: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
            ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f"{driver1} (Base)")
            ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f"{driver2} (Comp)")
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
            ax_t.plot(ref_tel['Distance'], ref_tel['Throttle'], color='cyan', alpha=0.8)
            ax_t.plot(comp_tel['Distance'], comp_tel['Throttle'], color='magenta', linestyle='--', alpha=0.8)
            ax_t.set_ylabel('Throttle (%)')
            ax_t.axhline(100, color='grey', linestyle=':', alpha=0.5)
            ax_t.grid(True, linestyle=':', alpha=0.3)
    
            # [Layer 4] 煞車層 (Brake)
            ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
            ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
            ax_b.set_ylabel('Brake')
            ax_b.set_xlabel('Distance (m)')
            ax_b.grid(True, linestyle=':', alpha=0.3)
    
            st.pyplot(fig)
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
    
            st.pyplot(fig_track)
            plt.close(fig_track)
            
        except Exception as e:
            logging.exception('Failed to render saved telemetry')
            st.error(f'圖表無法顯示：{e}')
    
            
    

    with tab2:
        st.subheader("戰情摘要")
        for column, code in zip(st.columns(2), [driver1, driver2]):
            info = drivers[code]
            column.markdown(f"**{code} — {info['name']}**")
            column.write(info["team"])
            column.metric("最快圈", format_lap(info["lap_seconds"]))
            lap_number = info["lap_number"]
            if lap_number is None:
                column.write("最快圈圈次：未提供")
            else:
                column.write(f"最快圈圈次：第 {lap_number} 圈")
            column.write(f"輪胎：{info['compound']}")
            tyre_life = info["tyre_life"]
            if tyre_life is None:
                column.write("最快圈胎齡：未提供")
            else:
                displayed_life = int(tyre_life) if tyre_life.is_integer() else round(tyre_life, 1)
                column.write(f"最快圈胎齡：{displayed_life} 圈")
        st.caption("圈次是該車手跑出最快圈時的比賽圈數；胎齡是當時該套輪胎的使用圈數。舊資料未包含時會標示未提供。")

with tab3:
    st.header("🏎️ F1 戰術數據全解析：互動式百科中心")
    st.markdown("歡迎來到 Fast1ap 知識庫！這裡收錄了從基礎遙測數據到 2026 最新車輛科技的所有名詞解釋。")
    
    # 嵌入擁有搜尋功能與三大分類的客製化百科 HTML
    encyclopedia_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {
            background-color: #0E1117; color: #E0E0E0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0; padding: 10px 20px;
        }
        /* 搜尋列設計 */
        .search-container { margin-bottom: 25px; }
        #searchInput {
            width: 100%; padding: 15px 20px; font-size: 1.1em;
            background-color: #1A1C23; color: white;
            border: 2px solid #2A2D35; border-radius: 8px;
            outline: none; transition: border-color 0.3s;
            box-sizing: border-box;
        }
        #searchInput:focus { border-color: #00FFFF; }
        
        /* 分類標題 */
        .category-title {
            color: #888; font-size: 0.95em; font-weight: bold;
            text-transform: uppercase; letter-spacing: 1.5px;
            margin-top: 30px; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px;
        }

        /* 卡片設計 */
        .card {
            background: linear-gradient(145deg, #16181f, #101216);
            border: 1px solid #2a2d35; border-left: 5px solid #333;
            border-radius: 8px; padding: 18px 20px; margin-bottom: 15px;
            cursor: pointer; overflow: hidden;
            transition: all 0.3s ease;
        }
        .card:hover { border-left-color: #00FFFF; transform: translateX(5px); background: #1a1c23; }
        .card.expanded { border-left-color: #FF00FF; background: #1a1c23; }
        
        .title { font-size: 1.15em; font-weight: 600; margin: 0; color: #FFF; display: flex; justify-content: space-between; }
        .icon { font-size: 1.2em; color: #666; transition: transform 0.4s ease; }
        .card.expanded .icon { transform: rotate(45deg); color: #FF00FF; }
        
        .content {
            max-height: 0; opacity: 0; transition: all 0.4s ease;
            color: #A0A0A0; line-height: 1.6; font-size: 1em;
        }
        .card.expanded .content { max-height: 600px; opacity: 1; margin-top: 15px; padding-top: 15px; border-top: 1px dashed #333; }
        
        /* 文字高光 */
        .cyan { color: #00FFFF; font-weight: 600; }
        .magenta { color: #FF00FF; font-weight: 600; }
        .green { color: #00FFCC; font-weight: bold; }
        .red { color: #FF4444; font-weight: bold; }
    </style>
    </head>
    <body>

        <div class="search-container">
            <input type="text" id="searchInput" onkeyup="filterCards()" placeholder="🔍 搜尋百科 (例如：時間差、輪胎、DRS)...">
        </div>

        <div id="encyclopedia">
            <div class="category-title">第一部分：核心遙測圖表解密</div>
            
            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">⏱️ Delta Time (時間差) <span class="icon">+</span></p>
                <div class="content">
                    <b>衡量誰正在贏得比賽的最強指標。</b><br>
                    透過演算法將兩車在賽道「同一距離點」的時間相減。我們圖表上的邏輯為：<br>
                    <span class="green">● 🟩 綠色曲線 (向上)</span>：基準車手 A 較快，正在拉開差距。<br>
                    <span class="red">● 🟥 紅色曲線 (向下)</span>：對比車手 B 較快，正在努力追趕。<br>
                    <i>*若斜率急遽變化，通常代表某方開啟了 DRS 或另一方發生了失誤。</i>
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">💨 Speed (時速與下壓力) <span class="icon">+</span></p>
                <div class="content">
                    <b>直線看引擎，彎道看空氣動力。</b><br>
                    最高點稱為 <span class="cyan">尾速 (Top Speed)</span>，取決於引擎馬力與車身低風阻。最低點稱為 <span class="magenta">彎中最低速 (Apex Speed)</span>，數值越高代表賽車擁有越強的下壓力 (Downforce) 把它死死按在地上，過彎能力越強。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🛑 Brake (煞車點與侵略性) <span class="icon">+</span></p>
                <div class="content">
                    <b>展現車手膽識的數據。</b><br>
                    圖表線條跳起代表車手重踩煞車。<span class="cyan">「晚煞車 (Late Braking)」</span>是最常見的超車技巧，比對手晚零點幾秒踩煞車，就能在入彎時搶佔內線。但若超過輪胎極限，就會導致煞車鎖死 (Lock-up) 衝出賽道。
                </div>
            </div>

            <div class="category-title">第二部分：賽道戰術與輪胎管理</div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🛞 輪胎配方 (Soft / Medium / Hard) <span class="icon">+</span></p>
                <div class="content">
                    F1 輪胎分為三種硬度，是決定比賽勝負的關鍵：<br>
                    ● <b>紅胎 (Soft 軟胎)</b>：抓地力最強、單圈最快，但磨損極快，通常用於排位賽或比賽末段衝刺。<br>
                    ● <b>黃胎 (Medium 中性胎)</b>：速度與耐用度的完美平衡。<br>
                    ● <b>白胎 (Hard 硬胎)</b>：非常耐磨，適合長距離作戰，但升溫慢且單圈速度最慢。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">📉 輪胎衰退 (Tyre Degradation / Deg) <span class="icon">+</span></p>
                <div class="content">
                    隨著行駛圈數增加，輪胎表面的橡膠會磨損、過熱，導致抓地力下降，這就是「衰退」。在我們的 Speed 圖表中，如果你看到車手在彎中的最低速越來越慢、煞車點越來越早，通常就是輪胎已經衰退的證明。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🔄 進站策略 (Pit Stop & Undercut) <span class="icon">+</span></p>
                <div class="content">
                    <b>Undercut (提前進站)</b> 是最經典的超車戰術。當你追不上前車時，選擇比他早一圈進站換上新輪胎。利用新輪胎強大的抓地力跑出極快的「出場圈 (Out-lap)」，當前車下一圈進站出來時，你就能利用這個時間差超越他。
                </div>
            </div>

            <div class="category-title">第三部分：2026 世代專屬黑科技</div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">✈️ 主動式空力套件 (Z-Mode & X-Mode) <span class="icon">+</span></p>
                <div class="content">
                    2026 賽車不再只有後尾翼能打開！<br>
                    ● <b>Z-Mode (高下壓力模式)</b>：過彎時預設使用，前後翼會提供最大抓地力。<br>
                    ● <b>X-Mode (低風阻模式)</b>：在大直線上由車手手動開啟，前後翼板會同時打開降低風阻，極速將大幅提升。在我們的 Speed 圖表大直線上，你能看出開啟 X-Mode 的驚人加速力。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">⚡ Manual Override (手動超車模式) <span class="icon">+</span></p>
                <div class="content">
                    2026 年取消了傳統的 DRS 超車規則，改為<b>電力超車模式</b>。<br>
                    當後車距離前車 1 秒內時，後車可以獲得額外的電能輸出額度 (高達 350kW)。這會反映在 Delta Time 曲線末段的急遽變化上，考驗車手在直線上對電池電量的極限壓榨。
                </div>
            </div>
        </div>

    <script>
        // 即時搜尋過濾功能
        function filterCards() {
            var input, filter, cards, title, content, i, txtValue;
            input = document.getElementById('searchInput');
            filter = input.value.toUpperCase();
            cards = document.getElementsByClassName('card');

            for (i = 0; i < cards.length; i++) {
                title = cards[i].querySelector(".title");
                content = cards[i].querySelector(".content");
                if (title || content) {
                    txtValue = title.textContent + " " + content.textContent;
                    if (txtValue.toUpperCase().indexOf(filter) > -1) {
                        cards[i].style.display = "";
                    } else {
                        cards[i].style.display = "none";
                    }
                }       
            }
        }
    </script>
    </body>
    </html>
    """
    
    # 增加高度以容納更多內容與搜尋列
    components.html(encyclopedia_html, height=750, scrolling=True)
   
