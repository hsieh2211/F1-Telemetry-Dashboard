"""Offline race-weekend guide; times are stored in UTC and displayed in Taipei."""
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from race_data import SESSION_NAMES, parse_utc
from season_content import load_season_content

TAIPEI = ZoneInfo("Asia/Taipei")
WEEKDAYS = "一二三四五六日"


def start_label(value):
    date = parse_utc(value)
    if date is None:
        return "時間待公布"
    local = date.astimezone(TAIPEI)
    return local.strftime("%Y/%m/%d") + f"（{WEEKDAYS[local.weekday()]}）" + local.strftime(" %H:%M")


def next_race(events, now=None):
    now = now or datetime.now(timezone.utc)
    upcoming = [(parse_utc(e["sessions"]["R"]["start_utc"]), e) for e in events]
    upcoming = [(date, event) for date, event in upcoming if date and date > now]
    return min(upcoming, key=lambda pair: pair[0])[1] if upcoming else None


def load_guides(root):
    data = load_season_content(root, 2026, "race_guides")
    if data.get("year") != 2026 or not isinstance(data.get("events"), dict):
        raise ValueError("賽事導覽格式無效")
    return data


def render_next_race(events, guides, now=None):
    event = next_race(events, now)
    if event:
        guide = guides.get("events", {}).get(event["event"], {})
        title = guide.get("title", event["event"])
        with st.container(border=True):
            st.caption("下一站｜台灣時間 Asia/Taipei")
            st.subheader(title, anchor="next-weekend")
            st.markdown(f"**正賽 {start_label(event['sessions']['R']['start_utc'])}**")
            for session in ("Q", "S"):
                if session in event["sessions"]:
                    st.caption(f"{SESSION_NAMES[session]} {start_label(event['sessions'][session]['start_utc'])}")
            for point in guide.get("watch", []):
                st.write(f"• {point}")
            if guide.get("source"):
                st.markdown(f"[官方本站賽程]({guide['source']})")
            st.caption(f"預定開始時間，日期已換算跨日；賽程核對：{guides.get('schedule_checked_on', guides.get('checked_on', '未提供'))}。觀賽重點為本站整理。")
    else:
        st.info("本地賽程中已無尚未到達預定開始時間的正賽；仍可查看完整賽曆與已保存的案例。")
    return event


def render_race_guide(event, code, guides, catalogue, now=None):
    guide = guides.get("events", {}).get(event["event"])
    st.subheader("這站怎麼看")
    if guide:
        st.markdown(f"**{guide['title']}｜{guide['venue']}**")
        st.write(guide["feature"])
    st.caption("開賽時間全部換算為台灣時間（Asia/Taipei）；日期已包含跨日。以下為預定開始時間，不是轉播開播時間。")
    now = now or datetime.now(timezone.utc)
    cards = []
    for session in ("S", "Q", "R"):
        if session not in event["sessions"]:
            continue
        value = event["sessions"][session]["start_utc"]
        start = parse_utc(value)
        status = "時間待公布" if start is None else ("排定時間已過" if start <= now else "預定開賽")
        selected = ' class="fp-session-current"' if session == code else ""
        cards.append(f'<li{selected}><span>{escape(SESSION_NAMES[session])}</span>'
                     f'<strong>{escape(start_label(value))}</strong><small>{status}</small></li>')
    st.html('<ul class="fp-session-times" aria-label="台灣時間賽程">' + "".join(cards) + '</ul>')
    st.caption("時間已過不代表已完賽；可否分析，以這個場次的離線資料驗證結果為準。衝刺賽與正賽排位是不同場次。")
    if guide:
        st.markdown("**觀賽先看這兩件事**")
        depth = st.radio("你想怎麼看這一站？", ["第一次看", "常看比賽", "深入查核"], horizontal=True, key="guide_depth")
        if depth == "第一次看":
            st.write(f"**先找畫面**： {guide['watch'][0]}")
            st.write("**再看動作**： 跟著一台車看完『減速 → 轉彎 → 加速』。出彎就是車子離開彎道、逐步加速的階段；別急著一次追全場。")
            st.write("**最後問一句**： 這個彎出口加速較順，下一段是否仍占優？切到『案例與分析』，有離線資料的場次可對照速度、油門與煞車。")
        elif depth == "常看比賽":
            for i, point in enumerate(guide["watch"], 1):
                st.write(f"{i}. {point}")
            st.write("**驗證攻防**： 先分清是排位單圈還是正賽跟車，再看前後車距、胎種、胎齡與進站前後位置。『案例與分析』的最快圈只能提供單圈線索，不能驗證整場策略。")
        else:
            st.write(f"**待驗證問題**： {guide['watch'][1]}")
            st.write("**需要的證據**： 同場逐圈時間、車距、輪胎使用段、進站與賽道狀態；判斷能量或空力模式還需要對應訊號。")
            st.write("**目前能查到**： 個人最快圈、匯出圈次與輪胎欄位，以及速度、油門、煞車取樣。尚未接入完整逐圈策略資料，不生成輪胎衰退率或進站收益結論。")
        st.caption("觀賽重點由本站依賽道特性整理；不是本場結果或策略預測。")
    with st.expander("完整賽曆與資料依據"):
        rows = []
        for item in catalogue["events"]:
            title = guides.get("events", {}).get(item["event"], {}).get("title", item["event"])
            rows.append({"分站": title, "正賽｜台灣時間": start_label(item["sessions"]["R"]["start_utc"]),
                         "排位｜台灣時間": start_label(item["sessions"]["Q"]["start_utc"]),
                         "衝刺｜台灣時間": start_label(item["sessions"]["S"]["start_utc"]) if "S" in item["sessions"] else "—"})
        st.dataframe(rows, hide_index=True, width="stretch")
        if guide:
            st.markdown(f"[F1 官方本站賽程與賽道介紹]({guide['source']})")
        st.markdown("[F1 官方完整賽曆](https://www.formula1.com/en/racing/2026)")
        st.caption(f"賽道介紹核對：{guides.get('checked_on', '未提供')}；賽程核對：{guides.get('schedule_checked_on', guides.get('checked_on', '未提供'))}。賽程為本地保存快照，可能調整；觀賽前請再確認官方本站頁面。")

