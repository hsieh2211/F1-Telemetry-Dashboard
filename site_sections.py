"""Dedicated destinations reuse the site's season-scoped content and data."""
import streamlit as st
from race_data import read_catalogue, existing_path, SESSION_NAMES
from race_guide import load_guides, render_race_guide
from homepage import beginner_section, render_glossary
from season_content import load_season_content
from season_profiles import render_profiles
from site_navigation import go_to


def section_style(root):
    st.html('<style>'+(root/'homepage.css').read_text(encoding='utf-8')+'</style>')


def render_calendar(root):
    section_style(root)
    st.title('2026 賽程與賽道')
    st.write('選一站，先看台灣時間與觀賽重點，再進入同場次的數據分析。')
    catalogue=read_catalogue(root/'data/schedule_2026.json')
    guides=load_guides(root)
    events=catalogue['events']
    index=st.session_state.get('home_event',17)
    if index not in range(len(events)):
        index=0
    left,right=st.columns([2,1])
    index=left.selectbox('選擇 2026 分站',range(len(events)),index=index,key='home_event',
                         format_func=lambda i:guides['events'].get(events[i]['event'],{}).get('title',events[i]['event']))
    event=events[index]
    codes=[code for code in SESSION_NAMES if code in event['sessions']]
    if st.session_state.get('home_session') not in codes:
        st.session_state['home_session']='R'
    code=right.selectbox('場次',codes,format_func=SESSION_NAMES.get,key='home_session')
    exists=existing_path(root,2026,event['event'],code).is_file()
    st.button('分析這個場次',key='calendar_analysis',on_click=go_to,args=('數據分析',),disabled=not exists,type='primary')
    if not exists:
        st.info('這個場次尚無離線最快圈檔案，可先閱讀賽道與賽程，或選擇其他已收錄場次。')
    render_race_guide(event,code,guides,catalogue)


def render_learning(root):
    section_style(root)
    st.title('2026 車迷入門')
    st.write('從基本問題開始，查名詞、認識車手與規則，再用真實數據練習判讀。')
    st.button('前往數據分析',key='learn_analysis',on_click=go_to,args=('數據分析',))
    beginner_section()
    render_glossary()
    render_profiles(root,2026,{})
    with st.expander('2026 賽車與規則'):
        learning=load_season_content(root,2026,'learning')
        st.caption(f"適用賽季：2026｜來源核對：{learning['checked_on']}。完整規定以 FIA 文件與當站公告為準。")
        for item in learning['rules']:
            st.markdown(f"**{item['title']}**")
            st.write(item['explanation'])
            st.caption(item['observe'])
        for source in learning['sources']:
            st.markdown(f"[{source['title']}]({source['url']})")
