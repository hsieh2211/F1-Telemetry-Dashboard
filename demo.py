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

# 建立資料快取 (優化效能)
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

# ----------------- 分頁 3: 賽車數據與戰術互動百科  -----------------
with tab3:
    st.header("🏎️ F1 戰術數據全解析：互動式百科中心")
    st.markdown("歡迎來到 Fast1ap 知識庫！這裡收錄了從基礎遙測數據到 2026 最新車輛科技的所有名詞解釋。")
    
    # 嵌入擁有搜尋功能與三大分類的客製化百科 HTML
    encyclopedia_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {
            background-color: #0E1117; color: #E0E0E0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0; padding: 10px 20px;
        }
        /* 搜尋列設計 */
        .search-container { margin-bottom: 25px; }
        #searchInput {
            width: 100%; padding: 15px 20px; font-size: 1.1em;
            background-color: #1A1C23; color: white;
            border: 2px solid #2A2D35; border-radius: 8px;
            outline: none; transition: border-color 0.3s;
            box-sizing: border-box;
        }
        #searchInput:focus { border-color: #00FFFF; }
        
        /* 分類標題 */
        .category-title {
            color: #888; font-size: 0.95em; font-weight: bold;
            text-transform: uppercase; letter-spacing: 1.5px;
            margin-top: 30px; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px;
        }

        /* 卡片設計 */
        .card {
            background: linear-gradient(145deg, #16181f, #101216);
            border: 1px solid #2a2d35; border-left: 5px solid #333;
            border-radius: 8px; padding: 18px 20px; margin-bottom: 15px;
            cursor: pointer; overflow: hidden;
            transition: all 0.3s ease;
        }
        .card:hover { border-left-color: #00FFFF; transform: translateX(5px); background: #1a1c23; }
        .card.expanded { border-left-color: #FF00FF; background: #1a1c23; }
        
        .title { font-size: 1.15em; font-weight: 600; margin: 0; color: #FFF; display: flex; justify-content: space-between; }
        .icon { font-size: 1.2em; color: #666; transition: transform 0.4s ease; }
        .card.expanded .icon { transform: rotate(45deg); color: #FF00FF; }
        
        .content {
            max-height: 0; opacity: 0; transition: all 0.4s ease;
            color: #A0A0A0; line-height: 1.6; font-size: 1em;
        }
        .card.expanded .content { max-height: 600px; opacity: 1; margin-top: 15px; padding-top: 15px; border-top: 1px dashed #333; }
        
        /* 文字高光 */
        .cyan { color: #00FFFF; font-weight: 600; }
        .magenta { color: #FF00FF; font-weight: 600; }
        .green { color: #00FFCC; font-weight: bold; }
        .red { color: #FF4444; font-weight: bold; }
    </style>
    </head>
    <body>

        <div class="search-container">
            <input type="text" id="searchInput" onkeyup="filterCards()" placeholder="🔍 搜尋百科 (例如：時間差、輪胎、DRS)...">
        </div>

        <div id="encyclopedia">
            <div class="category-title">第一部分：核心遙測圖表解密</div>
            
            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">⏱️ Delta Time (時間差) <span class="icon">+</span></p>
                <div class="content">
                    <b>衡量誰正在贏得比賽的最強指標。</b><br>
                    透過演算法將兩車在賽道「同一距離點」的時間相減。我們圖表上的邏輯為：<br>
                    <span class="green">● 🟩 綠色曲線 (向上)</span>：基準車手 A 較快，正在拉開差距。<br>
                    <span class="red">● 🟥 紅色曲線 (向下)</span>：對比車手 B 較快，正在努力追趕。<br>
                    <i>*若斜率急遽變化，通常代表某方開啟了 DRS 或另一方發生了失誤。</i>
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">💨 Speed (時速與下壓力) <span class="icon">+</span></p>
                <div class="content">
                    <b>直線看引擎，彎道看空氣動力。</b><br>
                    最高點稱為 <span class="cyan">尾速 (Top Speed)</span>，取決於引擎馬力與車身低風阻。最低點稱為 <span class="magenta">彎中最低速 (Apex Speed)</span>，數值越高代表賽車擁有越強的下壓力 (Downforce) 把它死死按在地上，過彎能力越強。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🛑 Brake (煞車點與侵略性) <span class="icon">+</span></p>
                <div class="content">
                    <b>展現車手膽識的數據。</b><br>
                    圖表線條跳起代表車手重踩煞車。<span class="cyan">「晚煞車 (Late Braking)」</span>是最常見的超車技巧，比對手晚零點幾秒踩煞車，就能在入彎時搶佔內線。但若超過輪胎極限，就會導致煞車鎖死 (Lock-up) 衝出賽道。
                </div>
            </div>

            <div class="category-title">第二部分：賽道戰術與輪胎管理</div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🛞 輪胎配方 (Soft / Medium / Hard) <span class="icon">+</span></p>
                <div class="content">
                    F1 輪胎分為三種硬度，是決定比賽勝負的關鍵：<br>
                    ● <b>紅胎 (Soft 軟胎)</b>：抓地力最強、單圈最快，但磨損極快，通常用於排位賽或比賽末段衝刺。<br>
                    ● <b>黃胎 (Medium 中性胎)</b>：速度與耐用度的完美平衡。<br>
                    ● <b>白胎 (Hard 硬胎)</b>：非常耐磨，適合長距離作戰，但升溫慢且單圈速度最慢。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">📉 輪胎衰退 (Tyre Degradation / Deg) <span class="icon">+</span></p>
                <div class="content">
                    隨著行駛圈數增加，輪胎表面的橡膠會磨損、過熱，導致抓地力下降，這就是「衰退」。在我們的 Speed 圖表中，如果你看到車手在彎中的最低速越來越慢、煞車點越來越早，通常就是輪胎已經衰退的證明。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">🔄 進站策略 (Pit Stop & Undercut) <span class="icon">+</span></p>
                <div class="content">
                    <b>Undercut (提前進站)</b> 是最經典的超車戰術。當你追不上前車時，選擇比他早一圈進站換上新輪胎。利用新輪胎強大的抓地力跑出極快的「出場圈 (Out-lap)」，當前車下一圈進站出來時，你就能利用這個時間差超越他。
                </div>
            </div>

            <div class="category-title">第三部分：2026 世代專屬黑科技</div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">✈️ 主動式空力套件 (Z-Mode & X-Mode) <span class="icon">+</span></p>
                <div class="content">
                    2026 賽車不再只有後尾翼能打開！<br>
                    ● <b>Z-Mode (高下壓力模式)</b>：過彎時預設使用，前後翼會提供最大抓地力。<br>
                    ● <b>X-Mode (低風阻模式)</b>：在大直線上由車手手動開啟，前後翼板會同時打開降低風阻，極速將大幅提升。在我們的 Speed 圖表大直線上，你能看出開啟 X-Mode 的驚人加速力。
                </div>
            </div>

            <div class="card" onclick="this.classList.toggle('expanded')">
                <p class="title">⚡ Manual Override (手動超車模式) <span class="icon">+</span></p>
                <div class="content">
                    2026 年取消了傳統的 DRS 超車規則，改為<b>電力超車模式</b>。<br>
                    當後車距離前車 1 秒內時，後車可以獲得額外的電能輸出額度 (高達 350kW)。這會反映在 Delta Time 曲線末段的急遽變化上，考驗車手在直線上對電池電量的極限壓榨。
                </div>
            </div>
        </div>

    <script>
        // 即時搜尋過濾功能
        function filterCards() {
            var input, filter, cards, title, content, i, txtValue;
            input = document.getElementById('searchInput');
            filter = input.value.toUpperCase();
            cards = document.getElementsByClassName('card');

            for (i = 0; i < cards.length; i++) {
                title = cards[i].querySelector(".title");
                content = cards[i].querySelector(".content");
                if (title || content) {
                    txtValue = title.textContent + " " + content.textContent;
                    if (txtValue.toUpperCase().indexOf(filter) > -1) {
                        cards[i].style.display = "";
                    } else {
                        cards[i].style.display = "none";
                    }
                }       
            }
        }
    </script>
    </body>
    </html>
    """
    
    # 增加高度以容納更多內容與搜尋列
    components.html(encyclopedia_html, height=750, scrolling=True)
