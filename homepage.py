"""Season-scoped landing page backed only by validated offline exports."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from race_data import read_catalogue, read_payload, existing_path, SESSION_NAMES


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
                <p class="fp-eyebrow">從認識，到深入</p>
                <h1 class="fp-title">每一圈，都有值得<br><span class="fp-title-accent">看懂的細節。</span></h1>
                <p class="fp-description">從你支持的車手，到一圈之間的差距。一起探索 <span class="fp-nowrap">Formula 1。</span></p>
                <nav class="fp-home-links" aria-label="首頁探索入口">
                    <a class="fp-primary-link" href="#season-races">探索本季賽事 ↓</a>
                    <a href="#getting-started">第一次看 F1 ↓</a>
                    <a href="#real-example">圖表怎麼看 ↓</a>
                </nav>
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
    st.header("2026 賽事與分析", anchor="season-races")
    st.caption("先選一站，再看一圈。分析範圍為各車手最快圈，並非整場逐圈資料。")
    featured = next((i for i, e in enumerate(events) if e["event"] == "United States Grand Prix"), 0)
    col1, col2 = st.columns([2, 1])
    index = col1.selectbox("選擇 2026 分站", range(len(events)), index=featured,
                           format_func=lambda i: events[i]["event"], key="home_event")
    event = events[index]
    codes = [c for c in SESSION_NAMES if c in event["sessions"]]
    code = col2.selectbox("場次", codes, format_func=SESSION_NAMES.get, key="home_session")
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
        if left.button("直接分析 →", type="primary", use_container_width=True):
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
        render_case(year, event["event"], code, drivers, available)

    st.header("認識 2026 賽場")
    st.caption("以下名單來自所選場次的離線資料，是該場參賽快照；不作為全季固定陣容或名次。")
    if case:
        with st.expander("車手與車隊：查看本場參賽名單"):
            st.dataframe([{"車手": f"{c} · {d['name']}", "車隊": d["team"]} for c, d in drivers.items()], hide_index=True, use_container_width=True)
    with st.expander("2026 賽車與規則"):
        st.info("當季規則專頁尚待核對官方文件後製作。目前只提供下方通用觀賽概念，不以舊年份規則代替 2026 規則。")
    beginner_section()
    st.divider()
    st.write("讓更多人在台灣，一起看懂 F1。")
    st.caption("獨立車迷專題，與 Formula 1 官方無隸屬關係。資料依賽季保存；目前首頁聚焦 2026。")


def render_case(year, event, code, drivers, available):
    st.header("最快圈比較快，代表整場也更快？", anchor="real-example")
    st.write("不一定。先用真實資料觀察一圈，再檢查比較條件。")
    st.caption(f"{year} · {event} · {SESSION_NAMES[code]}｜以下為所選場次真實離線資料。")
    a, b = st.columns(2)
    ref = a.selectbox("範例基準車手", available, key="case_a")
    comp = b.selectbox("範例比較車手", available, index=1, key="case_b")
    if ref == comp:
        st.info("請選擇兩位不同車手，才能觀察差異。")
        return
    d1, d2 = drivers[ref], drivers[comp]
    a.metric(f"{ref} 個人最快圈", f"{d1['lap_seconds']:.3f} 秒")
    b.metric(f"{comp} 個人最快圈", f"{d2['lap_seconds']:.3f} 秒")
    # Keep every offline sample; browser rendering preserves readable labels
    # and a fixed plotting height when the available width changes.
    samples = pd.concat([
        d["telemetry"][["Distance", "Speed"]].assign(Driver=c)
        for c, d in ((ref, d1), (comp, d2))
    ], ignore_index=True)
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
    else:
        st.write(f"取樣點數：{ref} {len(d1['telemetry'])} 點；{comp} {len(d2['telemetry'])} 點。")
        st.write("來源為 FastF1 匯出的個人最快圈。此圖直接繪製各圈自己的 Distance 與 Speed，未做共同 GPS 位置對齊；取樣與各圈積分距離差異會影響比較。")
        st.write("既有分析頁的時間差採各圈相對進度對齊後插值，屬近似值；不是官方分段計時。煞車只有 0／1 訊號，不代表踩踏力道。")


def beginner_section():
    st.header("第一次看 F1，從一個問題開始", anchor="getting-started")
    with st.expander("① 排位與正賽差在哪？"):
        st.write("排位主要爭取起跑位置；正賽爭取最終名次。起跑位置有利，不代表比賽結果已經決定。")
    with st.expander("② 為什麼要進站？"):
        st.write("進站可更換輪胎，但會付出時間；何時換胎需衡量輪胎狀況、與對手的差距及場上情況。")
    with st.expander("③ 最快圈、胎齡與遙測是什麼？"):
        st.write("最快圈：指定範圍內用時最短的一圈。胎齡：該套輪胎累積使用圈數，可能包含先前場次。遙測：速度、油門與煞車等行駛訊號。")
