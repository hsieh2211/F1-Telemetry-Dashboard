import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import os

# 1. 網頁頁面配置
st.set_page_config(page_title="Fast1ap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

# 2. 快取設定
if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# 3. 側邊欄與賽事選擇
st.sidebar.header("戰術控制中心")

# 修正：新手教學區 (更新正確的 Delta 邏輯)
with st.sidebar.expander("❓ 如何判讀數據？(新手指南)"):
    st.write("**Speed (時速)**: 曲線越高代表該路段尾速越快。")
    st.write("**Delta (時間差)**: 曲線往上代表「基準車手」拉開差距；往下代表「對手」正在追趕。")
    st.write("**Brake (煞車)**: 觀察車手入彎時踩下煞車的精確時機。")

type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

@st.cache_data
def get_session_data(s_type):
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner('正在分析數據...'):
    session = get_session_data(selected_type_code)

# ==========================================
# 🌟 重大修復：動態生成車手全名與車隊清單
# 不再手寫字典，直接從官方 API 的 results 抓取
# ==========================================
driver_map = {}
for index, row in session.results.iterrows():
    # 組合出例如： "George Russell (Mercedes)"
    driver_map[row['Abbreviation']] = f"{row['FullName']} ({row['TeamName']})"

driver_list = session.results['Abbreviation'].tolist()
# UI 選單使用動態字典
driver1 = st.sidebar.selectbox('2. 基準車手 (A)', driver_list, index=0, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, 'Unknown')}")
driver2 = st.sidebar.selectbox('3. 對比車手 (B)', driver_list, index=1, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, 'Unknown')}")

# 4. 數據分頁
tab1, tab2 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)"])

with tab1:
    try:
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        fig, (ax_s, ax_d, ax_b) = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # 第一層：時速
        ax_s.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
        ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f"{driver1} (Base)")
        ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f"{driver2} (Comp)")
        ax_s.set_ylabel('Speed (km/h)')
        ax_s.legend(loc='lower right')
        ax_s.grid(True, linestyle=':', alpha=0.3)

        # 第二層：Delta Time (🌟 重大修復：正負號與文字標籤)
        ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_d.axhline(0, color='grey', linestyle='--')
        
        # 修正 Y 軸標籤：正數代表基準車手(driver1)快，負數代表對比車手(driver2)快
        ax_d.set_ylabel(f'Delta (s)\n(+) {driver1} Faster\n(-) {driver2} Faster')
        
        # 填色維持：正數區塊(基準車手贏)我們改用紅色或自己喜歡的顏色，這裡維持紅綠對比
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)
        ax_d.grid(True, linestyle=':', alpha=0.3)

        # 第三層：煞車
        ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
        ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
        ax_b.set_ylabel('Brake')
        ax_b.set_xlabel('Distance (m)')
        ax_b.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)
        
        # 🌟 修正：最底下的中文防呆面板
        st.info(f"""
        **💡 Delta Time (時間差) 正確判讀指南：**
        這張圖表計算的是「{driver2} 減去 {driver1} 的時間差」。
        * 🟥 **紅色區塊 (曲線向上 / 正數)**：代表對手花費更多時間。這表示 **基準車手 {driver1} 比較快**，正在無情拉開差距！
        * 🟩 **綠色區塊 (曲線向下 / 負數)**：代表對手花費較少時間。這表示 **對手 {driver2} 比較快**，正在縮小差距。
        """)

    except Exception as e:
        st.error("此組合數據暫時無法載入。")
        st.write(e)

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
