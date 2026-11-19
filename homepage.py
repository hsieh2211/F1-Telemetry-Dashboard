"""Season-scoped landing page backed only by validated offline exports."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from race_data import read_catalogue, read_payload, existing_path, SESSION_NAMES
from race_guide import load_guides, render_next_race, render_race_guide
from season_content import load_season_content, comparison_flags, window_samples
from season_profiles import load_profiles, render_profiles, snapshot_rows


def taipei_time(value):
    if not value:
        return "未提供"
    if not isinstance(value, str):
        return "時間格式無效"
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            return "未提供時區"
        return date.astimezone(ZoneInfo("Asia/Taipei")).strftime("%Y/%m/%d %H:%M（台灣時間）")
    except (TypeError, ValueError):
        return "時間格式無效"


def open_analysis(index, code):
    st.session_state.update(page="analysis", event_index=index, session_code=code)
    st.rerun()


def choose_home_entry(section, index=None):
    """Apply a quick entry before its dependent widgets are instantiated."""
    st.session_state["home_section"] = section
    st.session_state["home_jump"] = {
        "賽程與賽道": "race-weekend", "2026 賽季知識": "getting-started", "案例與分析": "real-example"
    }[section]
    st.session_state["home_jump_id"] = st.session_state.get("home_jump_id", 0) + 1
    if index is not None:
        st.session_state.update(home_event=index, home_session="R")


def render_home(root):
    css = (root / "homepage.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
    # Avoid Markdown heading wrappers changing the hero grid and colors.
    st.html('''
        <div class="fp-brand">FASTLAP <span class="fp-brand-accent">PRO</span>
            <small>2026 賽季 · 繁體中文觀賽與數據</small>
        </div>
        <section class="fp-hero" aria-label="Fastlap Pro 2026 賽季介紹">
            <div class="fp-hero-copy">
                <p class="fp-eyebrow">讓更多人在台灣，一起看懂 F1</p>
                <h1 class="fp-title">2026 F1，<br><span class="fp-title-accent">從這一站看懂。</span></h1>
                <p class="fp-description">台灣時間賽程、繁中觀賽重點，與真實單圈資料帶讀。</p>
            </div>
            <div class="fp-year" aria-hidden="true">20<br>26</div>
        </section>
    ''')
    try:
        catalogue = read_catalogue(root / "data" / "schedule_2026.json")
        if catalogue["year"] != 2026:
            raise ValueError("此首頁只接受 2026 賽季資料")
    except (OSError, ValueError, TypeError, KeyError) as error:
        st.error(f"2026 賽程無法讀取：{error}")
        beginner_section()
        return

    events, year = catalogue["events"], catalogue["year"]
    try:
        guides = load_guides(root)
    except (OSError, ValueError, TypeError):
        guides = {}
    featured = next((i for i, e in enumerate(events) if e["event"] == "United States Grand Prix"), 0)
    upcoming = render_next_race(events, guides)
    next_entry, beginner_entry, case_entry = st.columns(3)
    if upcoming:
        next_entry.button("下一站賽程", key="home_next", use_container_width=True,
                          on_click=choose_home_entry, args=("賽程與賽道", events.index(upcoming)))
    else:
        next_entry.button("完整賽曆", key="home_calendar", use_container_width=True,
                          on_click=choose_home_entry, args=("賽程與賽道",))
    beginner_entry.button("新手從這裡開始", key="home_beginner", use_container_width=True,
                          on_click=choose_home_entry, args=("2026 賽季知識",))
    case_entry.button("看真實案例", key="home_case", use_container_width=True,
                      on_click=choose_home_entry, args=("案例與分析", featured))
    st.header("2026 賽事與分析", anchor="season-races")
    st.caption("下方為你選擇的分站；與上方下一站提示分開。分析使用個人最快圈。")
    col1, col2 = st.columns([2, 1])
    index = col1.selectbox("選擇 2026 分站", range(len(events)), index=featured,
                           format_func=lambda i: (guides.get("events", {}).get(events[i]["event"], {}).get("title", events[i]["event"]) + " · " + events[i]["event"]), key="home_event")
    event = events[index]
    codes = [c for c in SESSION_NAMES if c in event["sessions"]]
    code = col2.selectbox("場次", codes, format_func=SESSION_NAMES.get, key="home_session")
    case_tab, guide_tab, season_tab = st.tabs(["案例與分析", "賽程與賽道", "2026 賽季知識"], key="home_section", on_change="rerun")
    with case_tab:
        path = existing_path(root, year, event["event"], code)
        case = None
        if path.is_file():
            try:
                _, _, _, drivers, skipped = read_payload(path, (year, event["event"], code))
                metadata = json.loads(path.read_text(encoding="utf-8"))
                case = drivers, skipped, metadata
            except (OSError, ValueError, TypeError, KeyError) as error:
                st.error(f"此檔未通過檢查：{error}")
        else:
            st.info("此場次尚無離線資料；不代表賽事已完賽或已取消。")

        if case:
            drivers, skipped, metadata = case
            available = [c for c, d in drivers.items() if d["available"]]
            st.success(f"已讀取並驗證：{len(drivers)} 位車手名單，{len(available)} 位可比較最快圈。")
            left, right = st.columns(2)
            if left.button("直接分析 →", key="home_analysis", type="primary", use_container_width=True):
                open_analysis(index, code)
            right.markdown('[帶我看懂：閱讀下方真實資料範例 ↓](#real-example)')
            with st.expander("資料來源、匯出時間與缺漏"):
                st.write(f"來源：{metadata.get('source', '未註明')}；解析版本：{metadata.get('fastf1_version', '未註明')}")
                st.write(f"匯出時間：{taipei_time(metadata.get('exported_at'))}")
                st.caption("匯出時間不是比賽時間，也不是網站發布時間；驗證格式不能保證原始資料完全正確。")
                missing = []
                for c, d in drivers.items():
                    if not d["available"]:
                        missing.append(f"{c}：{d['reason']}")
                    else:
                        for key, label in (("lap_number", "圈次"), ("tyre_life", "胎齡"), ("compound", "胎種")):
                            if d.get(key) in (None, "", "None", "未知"):
                                missing.append(f"{c}：{label}未提供")
                for item in missing + skipped:
                    st.write(item)
                if not missing and not skipped:
                    st.write("本場有效車手的圈次、胎種與胎齡皆有值；驗證未跳過車手。")
                if metadata.get("skipped_drivers"):
                    st.write("匯出端紀錄：", metadata["skipped_drivers"])
            try:
                names = {c: d["name_zh"] for c, d in load_profiles(root, year)["drivers"].items()}
            except (OSError, ValueError, KeyError, TypeError):
                names = {}
            render_case(year, event["event"], code, drivers, available, names)

    with guide_tab:
        render_race_guide(event, code, guides, catalogue)
    with season_tab:
        st.header("認識 2026 賽場")
        beginner_section()
        render_glossary()
        render_profiles(root, year, drivers if case else {})
        st.caption("以下為所選場次的原始名單快照；不因本季介紹更新而覆蓋。")
        if case:
            with st.expander("車手與車隊：查看本場參賽名單"):
                st.dataframe(snapshot_rows(drivers), hide_index=True, use_container_width=True)
                st.caption("未提供代表匯出欄位缺漏；不以官方介紹靜默補寫原始紀錄。")
        with st.expander("2026 賽車與規則"):
            try:
                learning = load_season_content(root, year, "learning")
                st.caption(f"適用賽季：{year}｜來源核對：{learning['checked_on']}。以下是觀賽入門重點，完整規定及本站限制以 FIA 文件與當站公告為準。")
                for item in learning["rules"]:
                    st.markdown(f"**{item['title']}**")
                    st.write(item["explanation"])
                    st.caption(item["observe"])
                for source in learning["sources"]:
                    st.markdown(f"[{source['title']}]({source['url']})")
                st.caption("人物與車款入門介紹見本分頁上方；完整規章、每站升級套件與性能分析不包含在這份摘要。")
            except (OSError, ValueError, KeyError, TypeError):
                st.info("此賽季規則內容暫時無法讀取；不以其他年份內容替代。")
    st.divider()
    st.write("讓更多人在台灣，一起看懂 F1。")
    st.caption("獨立車迷專題，與 Formula 1 官方無隸屬關係。資料依賽季保存；目前首頁聚焦 2026。")
    jump = st.session_state.pop("home_jump", None)
    if jump:
        # Run only after a quick-entry click, once the selected panel is visible.
        # The revision makes repeat clicks on the same entry execute again.
        st.html(f'''<script>
        (() => {{
            const targetId = {json.dumps(jump)};
            const revision = {st.session_state["home_jump_id"]};
            const deadline = performance.now() + 8000;
            const seek = () => {{
                const target = document.getElementById(targetId);
                if (target && target.getClientRects().length && target.getBoundingClientRect().height) {{
                    requestAnimationFrame(() => target.scrollIntoView({{behavior: 'auto', block: 'start'}}));
                }} else if (performance.now() < deadline) {{
                    requestAnimationFrame(seek);
                }}
            }};
            requestAnimationFrame(seek);
        }})();
        </script>''', unsafe_allow_javascript=True)


def render_case(year, event, code, drivers, available, names=None):
    st.header("最快圈比較快，代表整場也更快？", anchor="real-example")
    st.write("不一定。先用真實資料觀察一圈，再檢查比較條件。")
    st.caption(f"{year} · {event} · {SESSION_NAMES[code]}｜以下為所選場次真實離線資料。")
    a, b = st.columns(2)
    names = names or {}
    def driver_label(c):
        name = names.get(c) or drivers[c].get("name")
        return c if name in (None, "", "None", "None None", "未知") else f"{c} · {name}"
    ref = a.selectbox("範例基準車手", available, format_func=driver_label, key="case_a")
    comp = b.selectbox("範例比較車手", available, index=1, format_func=driver_label, key="case_b")
    st.caption("選單姓名供辨識；比較使用所選場次原始資料，歷史名單不會因人物介紹而改寫。")
    if ref == comp:
        st.info("請選擇兩位不同車手，才能觀察差異。")
        return
    d1, d2 = drivers[ref], drivers[comp]
    a.metric(f"{ref} 個人最快圈", f"{d1['lap_seconds']:.3f} 秒")
    b.metric(f"{comp} 個人最快圈", f"{d2['lap_seconds']:.3f} 秒")
    phase = st.radio("跟著這個真實案例，一步一步看", ["1｜問題", "2｜證據", "3｜觀察", "4｜結論"], horizontal=True, key="walkthrough_step")
    render_walkthrough(phase, year, event, code, ref, comp, d1, d2)
    with st.expander("自由探索：速度、油門、煞車與比較方法", expanded=phase == "3｜觀察"):
        st.caption("上方為整圈用時；放大圖表不會把它改成區段用時。")
        st.markdown("**讀圖三步：找減速 → 對照動作 → 檢查比較條件。**")
        st.caption("橫軸是沿著各自這一圈累積的距離，縱軸是速度。曲線較高，只代表該取樣位置速度較高。")
        # Keep every offline sample; browser rendering preserves readable labels
        # and a fixed plotting height when the available width changes.
        samples = pd.concat([
            d["telemetry"][["Distance", "Speed", "Throttle", "Brake"]].assign(Driver=c)
            for c, d in ((ref, d1), (comp, d2))
        ], ignore_index=True)
        window = st.selectbox("放大閱讀範圍", ["整圈", "前 1/3", "中 1/3", "後 1/3"], key="case_window")
        samples = window_samples(samples, window)
        st.caption("三等分按整圈距離劃分，不是官方計時段，也未對應精確彎號。兩圈未以共同 GPS 位置對齊，不能據此精算煞車點差幾公尺。")
        if samples.empty or samples.groupby("Driver").size().reindex([ref, comp], fill_value=0).min() < 2:
            st.info("此距離區段沒有足夠的兩車取樣，請改選其他範圍。")
            return
        # Set finite domains from the actual samples so initial rendering does not
        # need to infer extents before Streamlit supplies the Arrow dataset.
        distance_domain = [float(samples["Distance"].min()), float(samples["Distance"].max())]
        speed_min, speed_max = float(samples["Speed"].min()), float(samples["Speed"].max())
        speed_padding = max((speed_max - speed_min) * .05, 1.0)
        speed_domain = [max(0.0, speed_min - speed_padding), speed_max + speed_padding]
        st.vega_lite_chart(samples, {
            "height": 300,
            "mark": {"type": "line", "strokeWidth": 2, "clip": True},
            "encoding": {
                "x": {"field": "Distance", "type": "quantitative",
                      "title": "距離（m）", "scale": {"domain": distance_domain, "nice": False},
                      "axis": {"tickCount": 5, "format": ",.0f"}},
                "y": {"field": "Speed", "type": "quantitative",
                      "title": "速度（km/h）",
                      "scale": {"domain": speed_domain, "zero": False, "nice": False},
                      "axis": {"tickCount": 5}},
                "color": {"field": "Driver", "type": "nominal", "title": None,
                          "scale": {"domain": [ref, comp], "range": ["#ff6558", "#f1f0ec"]},
                          "legend": {"orient": "top"}},
                "strokeDash": {"field": "Driver", "type": "nominal", "title": None,
                               "scale": {"domain": [ref, comp], "range": [[1, 0], [6, 4]]}},
                "tooltip": [
                    {"field": "Driver", "type": "nominal", "title": "車手"},
                    {"field": "Distance", "type": "quantitative", "title": "距離（m）", "format": ".0f"},
                    {"field": "Speed", "type": "quantitative", "title": "速度（km/h）", "format": ".1f"},
                ],
            },
            "config": {
                "axis": {"labelFontSize": 12, "titleFontSize": 13, "titlePadding": 10},
                "legend": {"labelFontSize": 13},
                "view": {"stroke": None},
            },
        }, width="stretch", key="home_speed_chart")
        with st.expander("對照駕駛動作：油門與煞車"):
            st.write("先找速度下降的位置，再對照煞車是否為 1、油門是否下降。煞車 1 只表示訊號啟用，不是踩踏力道；油門 100% 也不代表電力部署相同。")
            for channel, title, domain in (("Throttle", "油門（%）", [0, 100]), ("Brake", "煞車（0／1）", [0, 1])):
                signal = samples.copy()
                signal[channel] = signal[channel].astype(float)
                st.vega_lite_chart(signal, {
                    "height": 150,
                    "mark": {"type": "line", "interpolate": "step-after" if channel == "Brake" else "linear", "clip": True},
                    "encoding": {
                        "x": {"field": "Distance", "type": "quantitative", "title": "距離（m）", "scale": {"domain": distance_domain, "nice": False}, "axis": {"tickCount": 4}},
                        "y": {"field": channel, "type": "quantitative", "title": title, "scale": {"domain": domain}, "axis": {"values": [0, 1]} if channel == "Brake" else {"tickCount": 3}},
                        "color": {"field": "Driver", "type": "nominal", "title": None, "scale": {"domain": [ref, comp], "range": ["#ff6558", "#f1f0ec"]}, "legend": {"orient": "top"}},
                        "strokeDash": {"field": "Driver", "type": "nominal", "title": None},
                        "tooltip": [{"field": "Driver"}, {"field": "Distance", "format": ".0f"}, {"field": channel}],
                    },
                }, width="stretch", key=f"home_{channel}_chart")
            st.caption("曲線連線用於閱讀離散取樣；訊號切換發生在兩個樣本之間的確切位置未知。此檔未含電池荷電狀態、Overtake Mode 或主動空力模式訊號。")
        depth = st.radio("閱讀深度", ["先看懂", "看判讀", "查方法"], horizontal=True, key="case_depth")
        if depth == "先看懂":
            gap = abs(d1["lap_seconds"] - d2["lap_seconds"])
            if gap < .0005:
                st.write("兩人的個人最快圈用時相同（依匯出精度）。")
            else:
                faster = ref if d1["lap_seconds"] < d2["lap_seconds"] else comp
                st.write(f"這兩個個人最快圈中，{faster} 用時較少，相差 {gap:.3f} 秒。這不是完賽差距，也不能代表整場節奏。")
            st.write("曲線下降代表車速降低；煞車位置需要搭配煞車訊號，不能只看速度曲線。")
        elif depth == "看判讀":
            st.dataframe([{"車手": c, "最快圈圈次": d["lap_number"], "胎種": d["compound"], "胎齡（圈）": d["tyre_life"]} for c, d in ((ref, d1), (comp, d2))], hide_index=True, use_container_width=True)
            st.write("圈次、胎種與胎齡可能不同。油量、交通與當時賽道狀況未在此資料中提供，因此不能直接歸因為車手技巧或賽車性能。")
            notes = comparison_flags(d1, d2)
            for note in notes:
                st.warning(note)
            if not notes:
                st.info("這三個欄位相同，仍不能證明油量、交通、天候或能量部署相同。")
            st.write("**可以下的結論**： 這兩個個人最快圈各有什麼用時與取樣訊號。**還不能下的結論**： 誰整場更快、哪台車一定更好，或一次進站能賺幾秒。")
        else:
            st.write(f"取樣點數：{ref} {len(d1['telemetry'])} 點；{comp} {len(d2['telemetry'])} 點。")
            st.write("來源為 FastF1 匯出的個人最快圈。此圖直接繪製各圈自己的 Distance 與 Speed，未做共同 GPS 位置對齊；取樣與各圈積分距離差異會影響比較。")
            st.write("既有分析頁的時間差採各圈相對進度對齊後插值，屬近似值；不是官方分段計時。煞車只有 0／1 訊號，不代表踩踏力道。")


def render_walkthrough(phase, year, event, code, ref, comp, a, b):
    """One traceable lesson from the currently selected pair, never a race-result claim."""
    gap = abs(a["lap_seconds"] - b["lap_seconds"])
    finding = ("兩人的個人最快圈用時相同（依匯出精度）。" if gap < .0005 else
               f"{ref if a['lap_seconds'] < b['lap_seconds'] else comp} 的這個個人最快圈用時較少，相差 {gap:.3f} 秒。")
    if phase == "1｜問題":
        st.markdown("### 最快的一圈，就代表整場更快嗎？")
        st.write(f"現在比較的是 {year} 年 {event} 的{SESSION_NAMES[code]}：{ref}（{a['name']}）與 {comp}（{b['name']}）。")
        st.write(finding)
        st.write("先把『個人最快圈』想成一份單次成績。要判斷整場表現，還需要其他圈與比賽情境；接著選『2｜證據』，檢查這兩份成績的條件。")
    elif phase == "2｜證據":
        st.markdown("### 先核對，這兩圈是否在相近條件下跑出？")
        st.dataframe([{"車手": c, "個人最快圈（秒）": d["lap_seconds"], "圈次": d.get("lap_number"), "胎種": d.get("compound"), "胎齡（圈）": d.get("tyre_life")} for c, d in ((ref, a), (comp, b))], hide_index=True, width="stretch")
        notes = comparison_flags(a, b)
        if notes:
            for note in notes:
                st.warning(note)
        else:
            st.info("圈次、胎種與胎齡欄位相同；這仍不足以證明所有條件相同。")
        st.caption("胎齡是這套輪胎已使用的圈數，不是車手本場已跑的圈數。未提供的欄位保留缺漏。")
        st.write("油量、交通與能量部署未提供。下一步觀察動作，不把條件差異誤認為車手能力差距。")
    elif phase == "3｜觀察":
        st.markdown("### 找一處減速，再對照油門和煞車")
        st.write("下方選一段距離，先找速度曲線下降處，再展開『對照駕駛動作』：煞車是否切到 1？油門是否收小？一次只追一位車手，再看另一位。")
        st.write("看到訊號同時變化，可以描述取樣中的駕駛動作；兩圈未以共同 GPS 位置對齊，不能據此精算誰晚煞幾公尺，也不能單憑收油判定電池管理策略。")
    else:
        st.markdown("### 證據支持到這裡，就把結論停在這裡")
        st.success(finding)
        notes = comparison_flags(a, b)
        if notes:
            st.write("解讀時必須保留的條件：" + "；".join(notes))
        st.write("可以說：這兩個最快圈的用時與取樣訊號有何差異。還不能說：較快者整場更強、賽車一定更好，或某個進站策略一定有效。")
        st.markdown("**這次學到**：先核對比較條件，再描述差異；單次成績與整場表現是兩個不同問題。")
        st.markdown("**接著試試**：換成同隊兩位車手，重看『2｜證據』。同隊仍可能用不同胎種與胎齡；如果條件不近，就保留疑問。")
        st.caption(f"本例依 {year} · {event} · {SESSION_NAMES[code]} 的所選兩車資料即時生成；不是官方賽後戰報或完整逐圈分析。")


def beginner_section():
    st.header("第一次看 F1，從一個問題開始", anchor="getting-started")
    with st.expander("① 排位與正賽差在哪？"):
        st.write("排位主要爭取起跑位置；正賽爭取最終名次。起跑位置有利，不代表比賽結果已經決定。")
    with st.expander("② 為什麼要進站？"):
        st.write("進站可更換輪胎，但會付出時間；何時換胎需衡量輪胎狀況、與對手的差距及場上情況。")
    with st.expander("③ 最快圈、胎齡與遙測是什麼？"):
        st.write("最快圈：指定範圍內用時最短的一圈。胎齡：該套輪胎累積使用圈數，可能包含先前場次。遙測：速度、油門與煞車等行駛訊號。")


def render_glossary():
    st.subheader("數據名詞與讀圖說明", anchor="data-glossary")
    st.caption("先在這裡認識名詞，再進入數據比對。2026 模式與規則的官方來源見本分頁的『2026 賽車與規則』。")
    query = st.text_input("搜尋數據名詞", placeholder="例如：時間差、輪胎、煞車", key="glossary_search").strip().casefold()
    entries = [
        ("Delta Time｜時間差", "比較兩個單圈在行駛進度上的累積用時差。本工具以各圈起終點正規化後近似對齊，再插值比較；不是共同 GPS 位置的精確對齊，也不是正賽兩車的即時車距。"),
        ("Speed｜速度", "曲線高低表示取樣位置的車速。速度差可能與輪胎、油量、走線、交通、能量部署或設定有關，不能單靠尾速判斷引擎強弱，也不能以彎中速度直接量出下壓力。"),
        ("Throttle｜油門", "0～100% 表示油門訊號。油門全開不等於電力部署相同；目前匯出沒有電池電量或超車模式訊號。"),
        ("Brake｜煞車", "0 表示未啟用，1 表示啟用。這不是煞車壓力；訊號跳起不能解讀為重踩煞車，也不能單靠這個訊號評斷車手的侵略性。"),
        ("Compound｜輪胎配方", "SOFT（軟）、MEDIUM（中性）、HARD（硬）是本站乾地胎的相對分類；另有半雨胎與全雨胎。最快圈比較要核對胎種與胎齡，不能預設軟胎在所有情況都較快。"),
        ("Tyre Life｜胎齡", "這套輪胎已使用的圈數，不是車手本場跑過的總圈數。缺資料時保留未知，不把它視為新胎。"),
        ("Tyre Degradation｜輪胎衰退", "輪胎性能隨使用與狀況改變。要判斷衰退，需要連續圈速、同一套輪胎的使用段、交通與賽道狀態；一個最快圈或單次速度下降不足以證明輪胎衰退。"),
        ("Pit Stop／Undercut｜進站與提前換胎", "提前換胎可能利用新胎表現爭取位置，但也受暖胎、交通與進站損失影響。是否成功要看進站前後的實際位置及逐圈資料；本站最快圈不能驗證這項策略。"),
    ]
    matched = [(title, text) for title, text in entries if not query or query in (title + text).casefold()]
    if not matched:
        st.info("沒有找到這個名詞，請試試中文名稱或英文名稱。")
    for title, text in matched:
        with st.expander(title):
            st.write(text)
