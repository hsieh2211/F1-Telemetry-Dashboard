import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import os

# 1. 網頁基本設定與品牌形象
st.set_page_config(page_title="Fast1ap Pro - F1 Telemetry", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 賽道戰術數據儀表板')

# 2. 建立資料快取 (資工系優化效能必備)
if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# 3. 側邊欄：動態參數設定
st.sidebar.header("戰術控制中心")

# 比賽類型對照表
type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

# 數據載入函數 (支援動態切換 R/Q)
@st.cache_data
def get_f1_data(s_type):
    # 目前預設 2026 澳洲站，未來可擴充為年份/賽道選單
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner(f'正在同步 2026 澳洲站 {selected_type_label} 數據...'):
    session = get_f1_data(selected_type_code)

# 車手選擇
driver1 = st.sidebar.selectbox('2. 基準車手 (A)', session.results['Abbreviation'], index=0)
driver2 = st.sidebar.selectbox('3. 對比車手 (B)', session.results['Abbreviation'], index=1)

# 4. 建立分頁介面 (增加系統層次感)
tab1, tab2 = st.tabs(["📊 深度遙測對比 (含 Delta Time)", "📄 數據摘要"])

with tab1:
    try:
        # 抓取單圈數據
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        
        # 核心技術：使用 fastf1.utils 進行數據插值與對齊
        # 這解決了兩車距離點不一致的問題，產出精確的時間差 (Delta)
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        # 繪圖：三層式架構 (Speed / Delta / Brake)
        fig, (ax_speed, ax_delta, ax_brake) = plt.subplots(3, 1, figsize=(12, 10), 
                                                         height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # Layer 1: 時速 (Speed)
        ax_speed.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f'{driver1}')
        ax_speed.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f'{driver2}')
        ax_speed.set_ylabel('Speed (km/h)')
        ax_speed.legend(loc='lower right')
        ax_speed.grid(True, linestyle=':', alpha=0.3)
        ax_speed.set_title(f"Telemetry Comparison: {driver1} vs {driver2} ({selected_type_label})")

        # Layer 2: 時間差 (Delta Time) - 專題技術亮點
        ax_delta.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_delta.axhline(0, color='grey', linestyle='--')
        ax_delta.set_ylabel(f'Delta (s)\n<-- {driver2} Faster')
        # 填色邏輯：綠色區塊代表對手領先，紅色區塊代表基準領先
        ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
        ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)
        ax_delta.grid(True, linestyle=':', alpha=0.3)

        # Layer 3: 煞車 (Brake)
        ax_brake.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan', label=driver1)
        ax_brake.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5, label=driver2)
        ax_brake.set_ylabel('Brake')
        ax_brake.set_xlabel('Distance (m)')
        ax_brake.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)

    except Exception as e:
        st.error(f"分析失敗：請確認車手 {driver1} 與 {driver2} 在此節賽事中是否有完整數據。")
        st.info(f"錯誤訊息：{e}")

with tab2:
    st.subheader("比賽數據摘要")
    c1, c2 = st.columns(2)
    
    # 顯示車手最快圈速卡片
    try:
        c1.metric(f"{driver1} Lap Time", str(l1.LapTime)[10:19])
        c2.metric(f"{driver2} Lap Time", str(l2.LapTime)[10:19])
        
        st.write("---")
        # 顯示輪胎資訊
        st.write(f"🚗 **{driver1}** 使用輪胎: {l1['Compound']} ({int(l1['TyreLife'])} 圈)")
        st.write(f"🚗 **{driver2}** 使用輪胎: {l2['Compound']} ({int(l2['TyreLife'])} 圈)")
    except:
        st.warning("部分單圈細節無法讀取。")

# 5. 頁尾資訊
st.markdown("---")
st.caption("Data Source: FastF1 API | Project: F1 Telemetry & Strategy Insights")
