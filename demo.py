import streamlit as st
import fastf1
import matplotlib.pyplot as plt
import os

# 1. 網頁基本設定與品牌名稱
st.set_page_config(page_title="Fast1ap - 2026 F1 對比", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap: 2026 賽道戰術數據儀表板')
st.markdown("### 2026 澳洲站 - 雙車手遙測對比分析")

# 2. 建立快取資料夾
if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# 3. 抓取 2026 澳洲站數據
@st.cache_data
def get_2026_data():
    session = fastf1.get_session(2026, 'Australia', 'R')
    session.load()
    return session

with st.spinner('正在同步 2026 澳洲站官方數據...'):
    session = get_2026_data()

# 4. 側邊欄：雙車手與賽事類型設定
st.sidebar.header("設定")
session_type = st.sidebar.selectbox('選擇比賽類型', ['正賽 (Race)', '排位賽 (Qualifying)'])
driver1 = st.sidebar.selectbox('選擇車手 A (基準)', session.results['Abbreviation'], index=0)
driver2 = st.sidebar.selectbox('選擇車手 B (對手)', session.results['Abbreviation'], index=1)

# 5. 繪圖邏輯
try:
    l1 = session.laps.pick_drivers(driver1).pick_fastest()
    l2 = session.laps.pick_drivers(driver2).pick_fastest()
    
    t1 = l1.get_telemetry()
    t2 = l2.get_telemetry()

    fig, (ax_speed, ax_brake) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1], sharex=True)

    # 時速對比
    ax_speed.plot(t1['Distance'], t1['Speed'], color='cyan', label=f'{driver1} Speed')
    ax_speed.plot(t2['Distance'], t2['Speed'], color='magenta', label=f'{driver2} Speed', linestyle='--')
    ax_speed.set_ylabel('Speed (km/h)')
    ax_speed.legend()
    ax_speed.grid(True, linestyle=':', alpha=0.6)

    # 煞車對比
    ax_brake.plot(t1['Distance'], t1['Brake'], color='cyan', label=driver1)
    ax_brake.plot(t2['Distance'], t2['Brake'], color='magenta', alpha=0.5, label=driver2)
    ax_brake.set_ylabel('Brake')
    ax_brake.set_xlabel('Distance (m)')

    st.pyplot(fig)

    # 顯示時間卡片
    c1, c2 = st.columns(2)
    c1.metric(f"{driver1} 最快圈時間", str(l1.LapTime)[10:19])
    c2.metric(f"{driver2} 最快圈時間", str(l2.LapTime)[10:19])

except Exception as e:
    st.error("2026 數據對比失敗，請確認車手是否皆有完賽成績。")
