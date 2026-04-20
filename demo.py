import streamlit as st
import fastf1
import matplotlib.pyplot as plt
import os

# 1. 專業車手全名映射表 (解決 ANT 變螞蟻的誤會)
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

# 2. 網頁配置
st.set_page_config(page_title="Fast1ap Pro - 2026 F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

# 3. 側邊欄：戰術設定與新手說明
st.sidebar.header("戰術控制中心")

# 新手教學區 (教授最愛看的易用性設計)
with st.sidebar.expander("❓ 如何判讀數據？(新手指南)"):
    st.write("**Speed (時速)**: 曲線越高代表跑越快。")
    st.write("**Delta Time (時間差)**: 中間那層圖表。綠色代表對手在縮短差距。")
    st.write("**Brake (煞車)**: 觀察車手入彎時踩下煞車的精確時機。")

# 選單設定
type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

# 快取與資料下載
if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

@st.cache_data
def get_session_data(s_type):
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner('正在分析 2026 澳洲站數據...'):
    session = get_session_data(selected_type_code)

# 顯示全名的車手選單
driver_list = session.results['Abbreviation'].tolist()
driver1 = st.sidebar.selectbox('2. 基準車手 (A)', driver_list, index=0, 
                               format_func=lambda x: f"{x} - {DRIVER_NAMES.get(x, 'Unknown')}")
driver2 = st.sidebar.selectbox('3. 對比車手 (B)', driver_list, index=1, 
                               format_func=lambda x: f"{x} - {DRIVER_NAMES.get(x, 'Unknown')}")

# 4. 數據分頁
tab1, tab2 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)"])

with tab1:
    try:
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        fig, (ax_s, ax_d, ax_b) = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # 標題與繪圖 (改用英文代碼避免亂碼)
        ax_s.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
        
        ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=driver1)
        ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=driver2)
        ax_s.set_ylabel('Speed (km/h)')
        ax_s.legend()

        ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_d.axhline(0, color='grey', linestyle='--')
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)
        ax_d.set_ylabel('Delta Time (s)')

        ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
        ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
        ax_b.set_ylabel('Brake')
        ax_b.set_xlabel('Distance (m)')

        st.pyplot(fig)
        st.caption(f"註：基準車手 A ({driver1}) 使用青色線；對手 B ({driver2}) 使用洋紅虛線。")

    except:
        st.error("此組合數據暫時無法載入，請更換車手。")

with tab2:
    st.subheader("2026 澳洲大獎賽 戰情摘要")
    c1, c2 = st.columns(2)
    c1.metric(f"{driver1} 全名", DRIVER_NAMES.get(driver1, driver1))
    c2.metric(f"{driver2} 全名", DRIVER_NAMES.get(driver2, driver2))
    
    st.write("---")
    colA, colB = st.columns(2)
    colA.write(f"⏱️ **{driver1}** 最快圈: `{str(l1.LapTime)[10:19]}`")
    colA.write(f"🛞 輪胎: `{l1['Compound']}` ({int(l1['TyreLife'])} 圈)")
    
    colB.write(f"⏱️ **{driver2}** 最快圈: `{str(l2.LapTime)[10:19]}`")
    colB.write(f"🛞 輪胎: `{l2['Compound']}` ({int(l2['TyreLife'])} 圈)")

# 5. 頁尾
st.markdown("---")
st.caption("Data Source: FastF1 API | 中國科技大學資工系專題製作")
