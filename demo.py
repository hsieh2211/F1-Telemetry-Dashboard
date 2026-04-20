import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
import os

# ==========================================
# 1. 系統與品牌配置
# ==========================================
st.set_page_config(page_title="Fast1ap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

# 建立資料快取 (資工專題必備，優化效能)
if not os.path.exists('f1_cache'): 
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# ==========================================
# 2. 側邊欄控制中心
# ==========================================
st.sidebar.header("⚙️ 戰術控制中心")

# 比賽類型切換
type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

@st.cache_data
def get_session_data(s_type):
    # 目前預設 2026 澳洲站
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner(f'正在載入 2026 澳洲站 {selected_type_label} 數據...'):
    try:
        session = get_session_data(selected_type_code)
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        st.stop()

# 動態生成車手字典 (FullName + TeamName)
driver_map = {}
for index, row in session.results.iterrows():
    driver_map[row['Abbreviation']] = f"{row['FullName']} ({row['TeamName']})"

driver_list = session.results['Abbreviation'].tolist()

driver1 = st.sidebar.selectbox('2. 基準車手 (A)', driver_list, index=0, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, x)}")
driver2 = st.sidebar.selectbox('3. 對比車手 (B)', driver_list, index=1, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, x)}")

# ==========================================
# 3. 核心功能分頁 (包含互動百科)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)", "📖 互動式教學百科 (Guide)"])

# ----------------- 分頁 1: 戰術圖表 -----------------
with tab1:
    try:
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        fig, (ax_s, ax_d, ax_b) = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # [Layer 1] Speed
        ax_s.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
        ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f"{driver1} (Base)")
        ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f"{driver2} (Comp)")
        ax_s.set_ylabel('Speed (km/h)')
        ax_s.legend(loc='lower right')
        ax_s.grid(True, linestyle=':', alpha=0.3)

        # [Layer 2] Delta Time (正數=A贏/綠色, 負數=B贏/紅色)
        ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_d.axhline(0, color='grey', linestyle='--')
        ax_d.set_ylabel(f'Delta (s)\n(+) {driver1} Faster\n(-) {driver2} Faster')
        
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='green', alpha=0.3)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='red', alpha=0.3)
        ax_d.grid(True, linestyle=':', alpha=0.3)

        # [Layer 3] Brake
        ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
        ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
        ax_b.set_ylabel('Brake')
        ax_b.set_xlabel('Distance (m)')
        ax_b.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)
        
        st.info(f"""
        **💡 Delta Time (時間差) 判讀指南：**
        * 🟩 **綠色區塊 (曲線向上)**：代表 **{driver1}** 花費時間較少，正在拉開優勢。
        * 🟥 **紅色區塊 (曲線向下)**：代表 **{driver2}** 比較快，正在追趕或超越。
        """)

    except Exception as e:
        st.error("分析失敗：請確認車手是否皆有完賽成績。")

# ----------------- 分頁 2: 數據摘要 -----------------
with tab2:
    st.subheader("戰情摘要")
    c1, c2 = st.columns(2)
    c1.metric(f"{driver1}", driver_map.get(driver1, driver1))
    c2.metric(f"{driver2}", driver_map.get(driver2, driver2))
    
    st.write("---")
    colA, colB = st.columns(2)
    try:
        colA.write(f"⏱️ **{driver1}** 最快圈: `{str(l1.LapTime)[10:19]}`")
        colA.write(f"🛞 輪胎: `{l1['Compound']}` ({int(l1['TyreLife'])} 圈)")
        
        colB.write(f"⏱️ **{driver2}** 最快圈: `{str(l2.LapTime)[10:19]}`")
        colB.write(f"🛞 輪胎: `{l2['Compound']}` ({int(l2['TyreLife'])} 圈)")
    except:
        st.warning("無法獲取部分細節資料。")

# ----------------- 分頁 3: 帥氣互動百科 (Custom HTML/JS) -----------------
with tab3:
    st.header("🏎️ F1 戰術數據全解析：互動式教學面板")
    st.markdown("點擊下方卡片，探索各項遙測數據在 2026 賽季中的戰術意義。")
    
    encyclopedia_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body { background-color: #0E1117; color: white; font-family: sans-serif; margin: 0; padding: 10px; }
        .card {
            background-color: #1E1E1E;
            border-left: 5px solid #00FFFF;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .card:hover { transform: translateX(8px); background-color: #252525; border-left-color: #FF00FF; }
        .title { font-size: 1.1em; font-weight: bold; margin: 0; display: flex; justify-content: space-between; }
        .content { max-height: 0; overflow: hidden; transition: max-height 0.4s ease-out; color: #BBB; line-height: 1.5; }
        .expanded .content { max-height: 200px; margin-top: 10px; border-top: 1px solid #333; padding-top: 10px; }
        .green { color: #00FF00; font-weight: bold; }
        .red { color: #FF4444; font-weight: bold; }
    </style>
    </head>
    <body>
        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">⏱️ Delta Time (時間差) <span style="color:#555">▼</span></p>
            <div class="content">
                本系統的核心演算法。透過毫秒級插值對齊，計算兩車在同一位置的時間差。<br>
                <span class="green">● 綠色向上</span>：基準車手 A 比較快。<br>
                <span class="red">● 紅色向下</span>：對手 B 比較快。
            </div>
        </div>
        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">💨 Speed (時速分析) <span style="color:#555">▼</span></p>
            <div class="content">
                觀察大直線底的「尾速」與彎道中心的「最低速」。<br>
                2026 年新車導入主動式空力套件，直線阻力更小，尾速將比以往更高。
            </div>
        </div>
        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">🛑 Brake (煞車時機) <span style="color:#555">▼</span></p>
            <div class="content">
                顯示車手踩下煞車的精確距離點。<br>
                「晚煞車」是超車的關鍵，但也考驗車手對新世代動能回收系統 (ERS) 的操控。
            </div>
        </div>
        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">🔋 為什麼選擇 2026 賽季？ <span style="color:#555">▼</span></p>
            <div class="content">
                2026 是 F1 規則大改的一年，動力單元電力佔比提升至 50%。<br>
                開發此儀表板旨在幫助工程師即時分析新規則下的車輛動態差異。
            </div>
        </div>
    </body>
    </html>
    """
    components.html(encyclopedia_html, height=500)

# ==========================================
# 4. 系統頁尾
# ==========================================
st.markdown("---")
st.caption("Data Source: FastF1 API | F1 Telemetry & Strategy Insights Project v1.0")
