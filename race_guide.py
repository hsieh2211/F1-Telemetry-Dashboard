"""Offline race-weekend guide; times are stored in UTC and displayed in Taipei."""
import json
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from race_data import SESSION_NAMES, parse_utc

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
    data = json.loads((root / "data" / "race_guides_2026.json").read_text(encoding="utf-8"))
    if data.get("year") != 2026 or not isinstance(data.get("events"), dict):
        raise ValueError("賽事導覽格式無效")
    return data


def render_next_race(events, guides):
    event = next_race(events)
    if event:
        title = guides.get("events", {}).get(event["event"], {}).get("title", event["event"])
        st.caption(f"接下來的正賽｜{title} · {start_label(event['sessions']['R']['start_utc'])}（台灣時間）")
    else:
        st.caption("本地賽程中已無尚未到達預定開始時間的正賽。")


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
        for i, point in enumerate(guide["watch"], 1):
            st.write(f"{i}. {point}")
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
        st.caption(f"官方資料核對：{guides.get('checked_on', '未提供')}。賽程為本地保存快照，可能調整；觀賽前請再確認官方本站頁面。")

