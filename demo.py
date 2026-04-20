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

# ----------------- 分頁 3: 互動式教學百科  -----------------
with tab3:
    st.header("🏎️ F1 戰術數據全解析：高階遙測指南")
    st.markdown("歡迎來到 Fast1ap 數據中心！點擊下方資料卡，解密 2026 賽車物理極限。")
    
    pro_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {
            background-color: #0E1117; color: #E0E0E0; font-family: 'Segoe UI', sans-serif;
            margin: 0; padding: 15px;
        }
        .card {
            background: linear-gradient(145deg, #1a1c23, #121418);
            border: 1px solid #2a2d35;
            border-left: 6px solid #00FFFF;
            border-radius: 10px; padding: 20px; margin-bottom: 20px;
            cursor: pointer; overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 255, 255, 0.15);
            border-left-color: #FF00FF;
            background: linear-gradient(145deg, #1e2129, #15171c);
        }
        .title { font-size: 1.25em; font-weight: 600; margin: 0; color: #FFF; display: flex; justify-content: space-between; align-items: center; }
        .icon { transition: transform 0.4s ease; color: #888; font-size: 1.2em; }
        .card.expanded .icon { transform: rotate(180deg); color: #FF00FF; }
        .content {
            max-height: 0; opacity: 0; transition: all 0.4s ease;
            color: #B0B3B8; line-height: 1.7; font-size: 1.05em;
        }
        .card.expanded .content {
            max-height: 800px; opacity: 1; margin-top: 15px; padding-top: 15px;
            border-top: 1px dashed #3a3f4b;
        }
        .tag {
            display: inline-block; padding: 3px 8px; border-radius: 4px;
            font-size: 0.8em; font-weight: bold; margin-bottom: 12px; margin-right: 8px;
        }
        .tag-cyan { background: rgba(0, 255, 255, 0.1); color: #00FFFF; }
        .tag-magenta { background: rgba(255, 0, 255, 0.1); color: #FF00FF; }
        ul { margin-top: 10px; padding-left: 20px; }
        li { margin-bottom: 8px; }
        .green { color: #00FFCC; font-weight: 600; }
        .red { color: #FF4444; font-weight: 600; }
    </style>
    </head>
    <body>
        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">⏱️ Delta Time (時間差與微型區段) <span class="icon">▼</span></p>
            <div class="content">
                <span class="tag tag-cyan">核心演算法</span><span class="tag tag-magenta">戰術價值：極高</span><br>
                這是本系統最具價值的分析指標。我們不僅比較單圈總時間，而是透過空間插值對齊，將賽道切分成無數個「微區段」來相減。<br>
                <ul>
                    <li><span class="green">🟩 綠色曲線向上</span>：代表基準車手 (A) 在該路段花費的時間更少，正在無情拉開差距。</li>
                    <li><span class="red">🟥 紅色曲線向下</span>：代表對比車手 (B) 擁有更佳的牽引力或尾速，正在追趕。</li>
                </ul>
                <b>💡 工程師視角：</b>Delta Time 曲線斜率越陡，代表兩車在該路段的性能差異越巨大（通常發生在大直線的 DRS 開啟瞬間）。
            </div>
        </div>

        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">💨 Speed (時速與空力效率) <span class="icon">▼</span></p>
            <div class="content">
                <span class="tag tag-cyan">物理指標</span><br>
                遙測時速直接反映了賽車的引擎出力 (PU) 與空氣動力學效率 (Aero Efficiency)。<br>
                <ul>
                    <li><b>大直線尾速 (Top Speed)：</b>考驗 2026 世代 MGU-K 電池的電量分配策略。若曲線提早平緩，代表車輛發生「削波 (Clipping)」，電力已耗盡。</li>
                    <li><b>彎中最低速 (Apex Speed)：</b>圖表上呈 V 字型的谷底。數值越高，代表賽車擁有越強大的機械抓地力與下壓力。</li>
                </ul>
            </div>
        </div>

        <div class="card" onclick="this.classList.toggle('expanded')">
            <p class="title">🛑 Brake (煞車點與侵略性) <span class="icon">▼</span></p>
            <div class="content">
                <span class="tag tag-cyan">駕駛風格</span><br>
                這條曲線顯示了極速超過 300km/h 的賽車，在幾十公尺內急煞至 80km/h 的瞬間。<br>
                <ul>
                    <li><b>晚煞車 (Late Braking)：</b>在圖表上線條較晚跳起。這是最致命的超車武器，要求極高的輪胎溫度控制與膽識。</li>
                    <li><b>循跡煞車 (Trail Braking)：</b>煞車並非只是 0 與 1。優秀的車手會帶著些微煞車入彎，以維持前輪重量壓迫，增加轉向抓地力。</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(pro_html, height=600, scrolling=True)
