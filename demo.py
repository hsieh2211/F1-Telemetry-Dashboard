import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import os

# 1. 專業車手全名映射表
DRIVER_NAMES = {
    'VER': 'Max Verstappen (Red Bull)',
    'RUS': 'George Russell (Mercedes)',
    'ANT': 'Kimi Antonelli (Mercedes)',
    'HAM': 'Lewis Hamilton (Ferrari)',
    'NOR': 'Lando Norris (McLaren)',
    'PIA': 'Oscar Piastri (McLaren)',
    'LEC': 'Charles Leclerc (Ferrari)',
    'SAI': 'Carlos Sainz (Williams)',
    'ALO': 'Fernando Alonso (Aston Martin)'
}

# 2. 網頁頁面配置
st.set_page_config(page_title="Fast1ap Pro - 2026 F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

# 3. 側邊欄與賽事選擇
st.sidebar.header("戰術控制中心")

type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

@st.cache_data
def get_session_data(s_type):
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner('正在分析數據...'):
    session = get_session_data(selected_type_code)

# 動態生成車手清單
driver_map = {}
for index, row in session.results.iterrows():
    driver_map[row['Abbreviation']] = f"{row['FullName']} ({row['TeamName']})"

driver_list = session.results['Abbreviation'].tolist()
driver1 = st.sidebar.selectbox('2. 基準車手 (A)', driver_list, index=0, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, 'Unknown')}")
driver2 = st.sidebar.selectbox('3. 對比車手 (B)', driver_list, index=1, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, 'Unknown')}")

# ==========================================
# 🌟 重大升級：加入第三個百科分頁
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)", "📖 新手教學百科 (Guide)"])

with tab1:
    try:
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        fig, (ax_s, ax_d, ax_b) = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        ax_s.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
        ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f"{driver1} (Base)")
        ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f"{driver2} (Comp)")
        ax_s.set_ylabel('Speed (km/h)')
        ax_s.legend(loc='lower right')
        ax_s.grid(True, linestyle=':', alpha=0.3)

        ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_d.axhline(0, color='grey', linestyle='--')
        ax_d.set_ylabel(f'Delta (s)\n(+) {driver1} Faster\n(-) {driver2} Faster')
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)
        ax_d.grid(True, linestyle=':', alpha=0.3)

        ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
        ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
        ax_b.set_ylabel('Brake')
        ax_b.set_xlabel('Distance (m)')
        ax_b.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)
        
        st.info(f"""
        **💡 Delta Time (時間差) 判讀指南：** 🟥 **紅色區塊 (正數)**：{driver1} 較快，正在拉開差距。 | 🟩 **綠色區塊 (負數)**：{driver2} 較快，正在縮小差距。
        """)

    except Exception as e:
        st.error("此組合數據暫時無法載入。")

with tab2:
    st.subheader("戰情摘要")
    c1, c2 = st.columns(2)
    c1.metric(f"{driver1}", driver_map.get(driver1, driver1))
    c2.metric(f"{driver2}", driver_map.get(driver2, driver2))
    
    st.write("---")
    colA, colB = st.columns(2)
    try:
        colA.write(f"⏱️ **{driver1}** 最快圈: `{str(l1.LapTime)[10:19]}`")
        colB.write(f"⏱️ **{driver2}** 最快圈: `{str(l2.LapTime)[10:19]}`")
    except:
        pass

# ==========================================
# 🌟 實作百科內容 (使用 st.expander 做出點擊展開的互動感)
# ==========================================
with tab3:
    st.header("🏎️ F1 2026 戰術數據全解析：新手友善指南")
    st.markdown("歡迎來到 Fast1ap 數據中心！如果你是第一次看 F1 的數據圖，請參考以下的圖表解密。")
    
    st.subheader("📊 1. 三層圖表解碼")
    with st.expander("👉 Speed (時速)：直線有多快？"):
        st.write("最上層的圖表顯示賽車在賽道上的瞬間時速。**曲線的高點通常出現在大直線的末端**，這時賽車可能突破 330 km/h。當曲線急遽下降，代表賽車正在重踩煞車進入彎道。")
        
    with st.expander("👉 Delta Time (時間差)：誰在贏？ (最關鍵)"):
        st.write("中間的圖表是工程師最看重的數據。它將兩台車在賽道同一位置的時間相減：")
        st.write("- **紅色向上隆起**：代表基準車手表現更好，正在**無情拉開距離**。")
        st.write("- **綠色向下凹陷**：代表對手在這個路段跑得更快，正在**努力追趕**。")
        
    with st.expander("👉 Brake (煞車)：膽量對決"):
        st.write("最下方的圖表顯示車手何時踩下煞車。你可以藉此觀察兩人的**防守風格**。越晚踩煞車（線越晚跳起來）代表車手的侵略性越高，但也越容易錯過彎道頂點。")

    st.subheader("🏎️ 2. 關於 2026 新規範 (專題技術背景)")
    with st.expander("👉 為什麼 2026 數據很重要？"):
        st.write("2026 年 F1 迎來了巨大的規則改動，包含了**主動式空力套件 (Active Aero)** 與 **50% 電力驅動的全新 ERS 系統**。這代表過去的數據都不再適用，每一場比賽的遙測分析都成為了各車隊重新摸索物理極限的關鍵。這也是本資工專題開發此系統的核心動機。")

# 5. 頁尾
st.markdown("---")
st.caption("Data Source: FastF1 API | 中國科技大學資工系專題製作 - F1 Telemetry & Strategy Insights")
