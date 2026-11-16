"""Year-scoped, sourced introductions, separate from immutable race snapshots."""
import streamlit as st

from season_content import load_season_content


def load_profiles(root, year):
    data = load_season_content(root, year, "profiles")
    teams, drivers = data.get("teams"), data.get("drivers")
    if not isinstance(teams, dict) or not isinstance(drivers, dict) or not teams or not drivers:
        raise ValueError("賽季人物資料不完整")
    for key, team in teams.items():
        if not all(team.get(field) for field in ("name", "name_zh", "car", "power_unit", "base", "intro", "sources", "driver_codes")):
            raise ValueError("車隊或車款介紹不完整")
        if any(code not in drivers or key not in drivers[code]["teams"] for code in team["driver_codes"]):
            raise ValueError("車隊與車手關聯不一致")
    for code, driver in drivers.items():
        if not all(driver.get(field) for field in ("name", "name_zh", "nationality", "number", "teams", "intro", "sources")):
            raise ValueError("車手介紹不完整")
        if any(key not in teams or code not in teams[key]["driver_codes"] for key in driver["teams"]):
            raise ValueError("車手與車隊關聯不一致")
    return data


def known(value):
    return value if value not in (None, "", "None", "None None", "未知") else "未提供"


def snapshot_rows(snapshot):
    return [{"代碼": code, "匯出姓名": known(d.get("name")), "匯出車隊": known(d.get("team"))} for code, d in snapshot.items()]


def show_sources(sources, date):
    with st.expander("官方來源與核對日期"):
        for source in sources:
            st.markdown(f"[{source['title']}]({source['url']})")
        st.caption(f"核對日期：{date}。這是當季資料快照；官方網頁日後可能更新。")


def render_profiles(root, year, snapshot):
    try:
        data = load_profiles(root, year)
    except (OSError, ValueError, KeyError, TypeError):
        st.info("此賽季人物與賽車介紹暫時無法讀取，不以其他年份資料替代。")
        return
    teams, drivers = data["teams"], data["drivers"]
    st.subheader(f"{year} 車手、車隊與賽車", anchor="season-profiles")
    st.caption(f"收錄 {len(teams)} 支車隊、{len(teams)} 款當季賽車與 {len(drivers)} 位本季參賽車手（含代打與季中更替）；不是單站同時有 {len(drivers)} 台車。")
    st.caption("中文譯名供閱讀，官方英文名稱供核對。車型是底盤名稱；動力單元包含內燃機、電動馬達與能量回收等系統，兩者不是同一件事。")
    focus = st.radio("想先認識什麼？", ["車隊與賽車", "車手"], horizontal=True, key="profile_focus")
    if focus == "車隊與賽車":
        key = st.selectbox("選擇車隊", list(teams), format_func=lambda k: f"{teams[k]['name_zh']} · {teams[k]['name']}", key="profile_team")
        team = teams[key]
        st.markdown(f"### {team['name_zh']} · {team['name']}")
        a, b = st.columns(2)
        a.metric(f"{year} 車型", team["car"])
        b.metric("動力單元供應商", team["power_unit"])
        st.caption(f"車隊基地：{team['base']}")
        st.write(team["intro"])
        st.markdown("**本季關聯車手（含代打／更替）**")
        st.write("、".join(f"{drivers[c]['name_zh']}（{c}）" for c in team["driver_codes"]))
        if snapshot:
            entered = [c for c, d in snapshot.items() if d.get("team") == team["name"]]
            st.info("所選場次匯出名單中的本隊車手：" + ("、".join(entered) if entered else "無可核對的車隊欄位；請查看下方場次快照。"))
        st.caption("車型是當季底盤名稱，不代表全年使用完全相同的零件。相同動力單元供應商也不代表相同底盤或性能。")
        with st.expander("觀賽時，可以怎麼認識這支車隊？"):
            st.write("先在同一場次找到隊友，再核對圈次、胎種與胎齡後比較。若涉及代打或換隊，先看該場實際名單；不要把不同車隊時期的成績混成同一組隊友比較。")
            peers = [v["name"] for k, v in teams.items() if k != key and v["power_unit"] == team["power_unit"]]
            st.write("本季使用同一動力單元供應商的其他車隊：" + ("、".join(peers) if peers else "本介紹中沒有其他車隊。"))
        show_sources(team["sources"], data["checked_on"])
    else:
        code = st.selectbox("選擇車手", list(drivers), format_func=lambda c: f"{c} · {drivers[c]['name_zh']} · {drivers[c]['name']}", key="profile_driver")
        driver = drivers[code]
        st.markdown(f"### {driver['name_zh']} · {driver['name']}")
        st.caption(f"{driver['nationality']}｜{year} 車號 {driver['number']}｜代碼 {code}")
        st.write(driver["intro"])
        st.write(f"{year} 所屬／曾出賽車隊：" + "、".join(teams[k]["name"] for k in driver["teams"]))
        if code in snapshot:
            st.info(f"所選場次有 {code} 的名單紀錄；匯出車隊：{known(snapshot[code].get('team'))}。有名單不等於有有效最快圈。")
        elif snapshot:
            st.info(f"所選場次匯出名單沒有 {code}；不把他的其他場次資料加入這場比較。")
        st.caption("履歷中的過往年份是人物背景；車號與車隊關聯為本季核對資料。簡介不是即時排名，也不把車手固定貼上駕駛風格標籤。")
        show_sources(driver["sources"], data["checked_on"])
    with st.expander("本季車款與動力單元一覽"):
        st.dataframe([{"車隊": t["name"], f"{year} 車型": t["car"], "動力單元": t["power_unit"]} for t in teams.values()], hide_index=True, width="stretch")
        st.caption("為當季車型與供應商的入門對照，並非零件規格表或賽車強弱排名。")

