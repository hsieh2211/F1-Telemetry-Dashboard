import streamlit as st
import fastf1
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="F1 數據儀表板", page_icon="🏎️")
st.title('🏁 F1 賽道戰術數據儀表板')

# 1. 建立快取
if not os.path.exists('f1_cache'):
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# 2. 新增：選擇比賽類型的選單
st.sidebar.header("設定")
session_type = st.sidebar.selectbox('選擇比賽類型', ['正賽 (Race)', '排位賽 (Qualifying)'])
type_code = 'R' if session_type == '正賽 (Race)' else 'Q'

# 3. 讀取資料 (加上 session 類型的快取)
@st.cache_data
def load_session_data(t_code):
    session = fastf1.get_session(2026, 'Australia', t_code)
    session.load()
    return session

with st.spinner(f'正在讀取 2026 澳洲站 {session_type} 數據...'):
    session = load_session_data(type_code)

# 4. 自動抓取所有車手名單
driver_list = session.results['Abbreviation'].tolist()
st.subheader(f"2026 澳洲站 - {session_type} 遙測分析")
driver = st.selectbox('選擇車手', driver_list)

# 5. 繪圖
try:
    lap = session.laps.pick_drivers(driver).pick_fastest()
    telemetry = lap.get_telemetry()

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(telemetry['Distance'], telemetry['Speed'], color='blue', label='Speed')
    ax1.set_xlabel('Distance (m)')
    ax1.set_ylabel('Speed (km/h)', color='blue')
    
    ax2 = ax1.twinx()
    ax2.plot(telemetry['Distance'], telemetry['Brake'], color='red', linestyle='--', label='Brake')
    ax2.set_ylabel('Brake (0/1)', color='red')
    
    plt.title(f"{driver} - {session_type} Fastest Lap")
    st.pyplot(fig)
    
    # 顯示最快單圈時間，讓報告更專業
    st.write(f"⏱️ **{driver}** 在此場景的最快單圈時間為: **{lap.LapTime}**")

except Exception as e:
    st.error(f"暫無 {driver} 的數據。")