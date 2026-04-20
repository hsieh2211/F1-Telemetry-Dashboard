import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import os

# ==========================================
# 1. 系統與環境配置
# ==========================================
st.set_page_config(page_title="Fast1ap Pro - F1 Analytics", page_icon="🏎️", layout="wide")
st.title('🏁 Fast1ap Pro: 2026 賽道戰術數據儀表板')

if not os.path.exists('f1_cache'): 
    os.makedirs('f1_cache')
fastf1.Cache.enable_cache('f1_cache')

# ==========================================
# 2. 側邊欄控制中心 (動態參數設定)
# ==========================================
st.sidebar.header("⚙️ 戰術控制中心")

with st.sidebar.expander("❓ 快速判讀指南 (Quick Guide)"):
    st.write("**Speed (時速)**: 觀察大直線的尾速與進彎減速點。")
    st.write("**Delta (時間差)**: 綠色代表基準車手(A)拉開優勢；紅色代表對比車手(B)正在追趕。")
    st.write("**Brake (煞車)**: 觀察誰的煞車踩得更晚、更具侵略性。")

# 賽事類型切換 (解決中文亂碼，轉換為 API 專用代號)
type_mapping = {'正賽 (Race)': 'R', '排位賽 (Qualifying)': 'Q'}
selected_type_label = st.sidebar.selectbox('1. 選擇比賽類型', list(type_mapping.keys()))
selected_type_code = type_mapping[selected_type_label]

@st.cache_data
def get_session_data(s_type):
    # 預設載入 2026 澳洲站
    session = fastf1.get_session(2026, 'Australia', s_type)
    session.load()
    return session

with st.spinner(f'正在載入 2026 澳洲站 {selected_type_label} 官方遙測數據...'):
    try:
        session = get_session_data(selected_type_code)
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        st.stop()

# 動態生成車手全名與車隊字典 (解決新秀顯示 Unknown 的問題)
driver_map = {}
for index, row in session.results.iterrows():
    driver_map[row['Abbreviation']] = f"{row['FullName']} ({row['TeamName']})"

driver_list = session.results['Abbreviation'].tolist()

driver1 = st.sidebar.selectbox('2. 基準車手 (Base Driver A)', driver_list, index=0, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, x)}")
driver2 = st.sidebar.selectbox('3. 對比車手 (Comp Driver B)', driver_list, index=1, 
                               format_func=lambda x: f"{x} - {driver_map.get(x, x)}")

# ==========================================
# 3. 核心功能分頁 (UI 結構化)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 深度戰術分析 (Pro Analysis)", "📋 數據摘要 (Summary)", "📖 新手教學百科 (Guide)"])

# ----------------- 分頁 1: 戰術對比圖表 -----------------
with tab1:
    try:
        # 抓取雙方最快單圈
        l1 = session.laps.pick_drivers(driver1).pick_fastest()
        l2 = session.laps.pick_drivers(driver2).pick_fastest()
        
        # 核心演算法：毫秒級距離插值與時間差計算
        delta_time, ref_tel, comp_tel = fastf1.utils.delta_time(l1, l2)

        fig, (ax_s, ax_d, ax_b) = plt.subplots(3, 1, figsize=(12, 10), height_ratios=[3, 2, 1], sharex=True)
        plt.style.use('dark_background')

        # [Layer 1] 時速圖 (Speed)
        ax_s.set_title(f"2026 Australia GP: {driver1} vs {driver2} ({selected_type_code})", fontsize=14)
        ax_s.plot(ref_tel['Distance'], ref_tel['Speed'], color='cyan', label=f"{driver1} (Base)")
        ax_s.plot(comp_tel['Distance'], comp_tel['Speed'], color='magenta', linestyle='--', label=f"{driver2} (Comp)")
        ax_s.set_ylabel('Speed (km/h)')
        ax_s.legend(loc='lower right')
        ax_s.grid(True, linestyle=':', alpha=0.3)

        # [Layer 2] 時間差圖 (Delta Time) - 邏輯與視覺完全統一版
        ax_d.plot(ref_tel['Distance'], delta_time, color='white', linewidth=1)
        ax_d.axhline(0, color='grey', linestyle='--')
        
        # 明確的 Y 軸防呆標籤
        ax_d.set_ylabel(f'Delta (s)\n(+) {driver1} Faster\n(-) {driver2} Faster')
        
        # 填色邏輯：正數代表 A 快(綠色)，負數代表 B 快(紅色)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time > 0), color='green', alpha=0.3)
        ax_d.fill_between(ref_tel['Distance'], delta_time, 0, where=(delta_time < 0), color='red', alpha=0.3)
        ax_d.grid(True, linestyle=':', alpha=0.3)

        # [Layer 3] 煞車圖 (Brake)
        ax_b.plot(ref_tel['Distance'], ref_tel['Brake'], color='cyan')
        ax_b.plot(comp_tel['Distance'], comp_tel['Brake'], color='magenta', alpha=0.5)
        ax_b.set_ylabel('Brake')
        ax_b.set_xlabel('Distance (m)')
        ax_b.grid(True, linestyle=':', alpha=0.3)

        st.pyplot(fig)
        
        # 中文防呆解讀面板 (內容與上方圖表邏輯 100% 吻合)
        st.info(f"""
        **💡 Delta Time (時間差) 精確判讀指南：**
        這張圖表是以 **{driver1} (基準車手，青色線)** 的視角出發，比較他與 **{driver2} (對比車手，洋紅虛線)** 的時間差距。
        * 🟩 **綠色區塊 (曲線向上 / 數值大於 0)**：代表 **{driver1}** 在該路段花費時間較少，速度較快，正在無情拉開優勢！
        * 🟥 **紅色區塊 (曲線向下 / 數值小於 0)**：代表 **{driver1}** 損失了時間，**對手 {driver2}** 比較快，正在努力追趕！
        """)

    except Exception as e:
        st.error(f"此組合數據暫時無法載入，請確認車手在此賽事階段是否皆有有效成績。")

# ----------------- 分頁 2: 數據摘要 -----------------
with tab2:
    st.subheader("🏎️ 戰情摘要與單圈資訊")
    c1, c2 = st.columns(2)
    c1.metric(f"基準車手 (A)", driver_map.get(driver1, driver1))
    c2.metric(f"對比車手 (B)", driver_map.get(driver2, driver2))
    
    st.write("---")
    colA, colB = st.columns(2)
    try:
        colA.write(f"⏱️ **{driver1}** 最快圈: `{str(l1.LapTime)[10:19]}`")
        colA.write(f"🛞 輪胎配方: `{l1['Compound']}` (已使用 {int(l1['TyreLife'])} 圈)")
        
        colB.write(f"⏱️ **{driver2}** 最快圈: `{str(l2.LapTime)[10:19]}`")
        colB.write(f"🛞 輪胎配方: `{l2['Compound']}` (已使用 {int(l2['TyreLife'])} 圈)")
    except:
        st.warning("無法讀取完整的單圈或輪胎資訊。")

# ----------------- 分頁 3: 專題教學百科 -----------------
with tab3:
    st.header("🏎️ F1 戰術數據全解析：新手友善指南")
    st.markdown("歡迎來到 Fast1ap 數據中心！如果你是第一次接觸 F1 遙測分析 (Telemetry)，請參考以下解密。")
    
    st.subheader("📊 1. 三層圖表解碼")
    with st.expander("👉 Speed (時速)：直線有多快？彎道極限在哪？"):
        st.write("最上層的圖表顯示賽車在賽道上的瞬間時速。**曲線的高點通常出現在大直線的末端**。當曲線急遽下降形成一個「V 型」，代表賽車正在重踩煞車進入彎道。你可以觀察兩位車手誰的彎中最低速 (Apex Speed) 比較高。")
        
    with st.expander("👉 Delta Time (時間差)：誰在贏？ (最關鍵指標)"):
        st.write("中間的圖表是賽事工程師最看重的數據。它透過線性插值 (Interpolation)，將兩台車在賽道同一距離點的時間相減：")
        st.write("- **綠色向上隆起**：代表基準車手表現更好，正在拉開距離。")
        st.write("- **紅色向下凹陷**：代表對手在這個路段跑得更快，正在縮短差距。")
        
    with st.expander("👉 Brake (煞車)：膽量與技術的對決"):
        st.write("最下方的圖表顯示車手何時踩下煞車。越晚踩煞車（線越晚跳起來）代表車手在進彎時的侵略性越高（Late Braking），這通常是超車的關鍵時刻。")

    st.subheader("⚙️ 2. 關於 2026 新規範 (專題開發背景)")
    with st.expander("👉 為什麼我們需要建置這套系統？"):
        st.write("2026 年 F1 迎來了巨大的規則改動，包含了**主動式空力套件 (Active Aero)** 與 **50% 電力驅動的全新 ERS 系統**。這代表過去的車輛動態數據都不再適用。這套儀表板旨在透過開源 API 數據，即時還原 2026 新世代賽車在賽道上的物理極限。")

# ==========================================
# 4. 系統頁尾
# ==========================================
st.markdown("---")
st.caption("Data Source: FastF1 API | Developed by NTUT CSIE Project Team - F1 Telemetry & Strategy Insights")
