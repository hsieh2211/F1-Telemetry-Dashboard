import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import numpy as np
import os

# 1. 品牌與頁面設定
st.set_page_config(page_title="Fast1ap Pro - 2026 Delta", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 深度戰術分析')
st.markdown("### 2026 澳洲站 - 毫秒級時間差 (Delta) 追蹤")

# 2. 快取與數據載入
if not os.path.exists('f1_cache'): os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

@st.cache_data
def get_2026_data():
    session = fastf1.get_session(2026, 'Australia', 'R')
    session.load()
    return session

session = get_2026_data()

# 3. 側邊欄設定
st.sidebar.header("分析參數")
driver1 = st.sidebar.selectbox('基準車手 (Reference)', session.results['Abbreviation'], index=0)
driver2 = st.sidebar.selectbox('對比車手 (Comparison)', session.results['Abbreviation'], index=1)

# 4. 核心邏輯：計算 Delta Time
try:
    l1 = session.laps.pick_drivers(driver1).pick_fastest()
    l2 = session.laps.pick_drivers(driver2).pick_fastest()
    
    # 取得遙測數據並進行對齊
    telemetry1 = l1.get_telemetry().add_distance()
    telemetry2 = l2.get_telemetry().add_distance()

    # 使用 FastF1 內建工具計算兩車時間差 (Delta)
    delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

    # 建立三層圖表：Speed, Brake, Delta
    fig, (ax_speed, ax_delta, ax_brake) = plt.subplots(3, 1, figsize=(12, 10), 
                                                     height_ratios=[3, 2, 1], sharex=True)

    # 上圖：Speed
    ax_speed.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=driver1)
    ax_speed.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=driver2)
    ax_speed.set_ylabel('Speed (km/h)')
    ax_speed.legend(loc='lower right')
    ax_speed.set_title(f'2026 Australia: {driver1} vs {driver2} Professional Analysis')

    # 中圖：Delta Time (關鍵加分項！)
    ax_delta.plot(ref_tel['Distance'], delta_time, color='white', linewidth=2)
    ax_delta.axhline(0, color='grey', linestyle='--')
    ax_delta.set_ylabel(f'Delta (s) <+ {driver2} slower | - {driver2} faster>')
    ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='red', alpha=0.3)
    ax_delta.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='green', alpha=0.3)

    # 下圖：Brake
    ax_brake.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
    ax_brake.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
    ax_brake.set_ylabel('Brake')
    ax_brake.set_xlabel('Distance (m)')

    plt.style.use('dark_background')
    st.pyplot(fig)

    # 數據摘要
    st.info(f"💡 圖表中間的綠色區塊代表 {driver2} 在該路段比 {driver1} 快；紅色則代表較慢。")

except Exception as e:
    st.error(f"數據計算錯誤: {e}")
