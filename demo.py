import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import os

# 1. 網頁頁面配置
st.set_page_config(page_title="Fast1ap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

# 2. 建立資料快取系統 (資工系專案必備)
if not os.path.exists('f1_cache'): 
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# 3. 側邊欄控制中心
st.sidebar.header("戰術控制中心 (Strategy Control)")

# 比賽類型對應 (代號對應 R/Q 避免圖表中文亂碼)
type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇賽事階段', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

@st.cache_data
def get_f1_session_data(s_type):
    # 預設載入 2026 澳洲站數據
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner(f'正在同步 2026 澳洲站數據...'):
    try:
        session = get_f1_session_data(selected_type_code)
    except Exception as e:
        st.error(f"無法載入數據: {e}")
        st.stop()

# 車手選擇選單
driver1 = st.sidebar.selectbox('2. 基準車手 (Reference)', session.results['Abbreviation'], index=0)
driver2 = st.sidebar.selectbox('3. 對比車手 (Comparison)', session.results['Abbreviation'], index=1)

# 4. 建立分頁介面 (解決顯示雜亂問題)
tab1, tab2 = st.tabs(["📊 Analysis (遙測對比)", "📄 Summary (數據摘要)"])

with tab1:
    try:
        # 提取最快單圈
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        
        # 關鍵技術：數據插值與對齊 (Interpolation)
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        # 建立三層繪圖架構
        fig, (ax_speed, ax_delta, ax_brake) = plt.subplots(3, 1, figsize=(12, 10), 
                                                         height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # 第一層：Speed (時速)
        ax_speed.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f'{driver1}')
        ax_speed.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f'{driver2}')
        ax_speed.set_ylabel('Speed (km/h)')
        ax_speed.legend(loc='lower right')
        ax_speed.grid(True, linestyle=':', alpha=0.3)
        # 注意：標題使用英文代碼避免框框亂碼
        ax_speed.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)

        # 第二層：Delta Time (時間差)
        ax_delta.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_delta.axhline(0, color='grey', linestyle='--')
        ax_delta.set_ylabel(f'Delta (s)\n<-- {driver2} Faster')
        # 填色區分領先(綠)與落後(紅)
        ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
        ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)
        ax_delta.grid(True, linestyle=':', alpha=0.3)

        # 第三層：Brake (煞車)
        ax_brake.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan', label=driver1)
        ax_brake.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5, label=driver2)
        ax_brake.set_ylabel('Brake')
        ax_brake.set_xlabel('Distance (m)')
        ax_brake.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)

    except Exception as e:
        st.error(f"分析失敗：數據不足。可能是該名車手未完成該節賽事。")
        st.info(f"技術錯誤訊息：{e}")

with tab2:
    st.subheader("Race Information Summary")
    c1, c2 = st.columns(2)
    
    try:
        # 顯示車手最快圈速
        c1.metric(f"{driver1} Lap Time", str(l1.LapTime)[10:19])
        c2.metric(f"{driver2} Lap Time", str(l2.LapTime)[10:19])
        
        st.write("---")
        # 輪胎資訊
        st.write(f"🏎️ **{driver1}**: 使用 {l1['Compound']} 胎 (已使用 {int(l1['TyreLife'])} 圈)")
        st.write(f"🏎️ **{driver2}**: 使用 {l2['Compound']} 胎 (已使用 {int(l2['TyreLife'])} 圈)")
    except:
        st.warning("無法獲取部分單圈細節資料。")

# 5. 底部版權聲明
st.markdown("---")
st.caption("Data: FastF1 API | Built for Senior Graduation Project 2026")
