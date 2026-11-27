"""Shared navigation and validated, refreshable links for the 2026 site."""
import re
from urllib.parse import urlencode
import streamlit as st
from race_data import read_catalogue

VIEWS = {'觀賽首頁':'home', '賽程與賽道':'calendar', '車迷入門':'learn', '數據分析':'analysis'}
TABS = ['最快圈比對','整場節奏與輪胎','單圈資料']
QUERY_KEYS = ('year','event','session','a','b','large')
BASE_URL = 'https://f1-telemetry-dashboard-gjhcvpyqwiuphhtx3vdnu2.streamlit.app/'


def slug(event):
    return re.sub(r'[^a-z0-9]+','_',event.lower()).strip('_')


def query_signature(query):
    return tuple((k,str(query.get(k,''))) for k in ('site_view','analysis_tab')+QUERY_KEYS)


def decode_link(query, catalogue):
    """Only catalogue identities, supported sessions and bounded codes are used."""
    events = catalogue['events']
    featured = next((i for i,e in enumerate(events) if e['event']=='United States Grand Prix'),0)
    notices=[]
    if query.get('year','2026')!='2026':
        notices.append('目前只開放 2026 賽季；連結未切換到其他年份。')
    view=query.get('site_view','觀賽首頁')
    if view not in VIEWS:
        notices.append('連結的頁面不存在，已回到觀賽首頁。')
        view='觀賽首頁'
    lookup={slug(e['event']):i for i,e in enumerate(events)}
    requested=query.get('event')
    index=lookup.get(requested,featured)
    if requested and requested not in lookup:
        notices.append('連結的分站不存在，已改用美國站。')
    code=query.get('session','R')
    if code not in events[index]['sessions']:
        notices.append('此分站沒有連結指定的場次，已改用正賽。')
        code='R'
    def driver(key):
        value=query.get(key)
        if value and re.fullmatch('[A-Z]{3}',value):
            return value
        if value:
            notices.append('連結的車手代碼格式無效，將使用可用車手。')
        return None
    tab=query.get('analysis_tab',TABS[0])
    if tab not in TABS:
        tab=TABS[0]
    return dict(view=view,index=index,code=code,a=driver('a'),b=driver('b'),tab=tab,large=query.get('large')=='1'),notices


def current_selection():
    previous=st.session_state.get('_route_selection',{})
    analysis=st.session_state.get('page')=='analysis'
    def value(key,fallback):
        result=st.session_state.get(key)
        return previous.get(fallback) if result is None else result
    return dict(index=value('event_index' if analysis else 'home_event','index'),
                code=value('session_code' if analysis else 'home_session','code') or 'R',
                a=value('analysis_a' if analysis else 'case_a','a'),
                b=value('analysis_b' if analysis else 'case_b','b'))


def mirror_selection(selection):
    for source,keys in [('index',('event_index','home_event')),('code',('session_code','home_session')),
                        ('a',('analysis_a','case_a')),('b',('analysis_b','case_b'))]:
        if selection.get(source) is not None:
            for key in keys:
                st.session_state[key]=selection[source]


def go_to(view):
    selection=current_selection()
    mirror_selection(selection)
    st.session_state['_route_selection']=selection
    st.session_state['site_view']=view
    st.session_state['page']=VIEWS[view]
    if view=='觀賽首頁':
        st.session_state['home_section']='案例與分析'


def on_nav_change():
    go_to(st.session_state['site_view'])


def restore_link(root):
    query=st.query_params.to_dict()
    signature=query_signature(query)
    last=st.session_state.get('_route_query')
    # Native tab binding has already restored its own value. A tab-only URL
    # change must not reinterpret an omitted/default navigation parameter as
    # a request to leave the current analysis destination.
    if last is not None:
        changed={key for (key,value),(_,old) in zip(signature,last) if value!=old}
        if changed=={'analysis_tab'}:
            st.session_state['_route_query']=signature
            return
    explicit=any(k in query for k in ('site_view','analysis_tab')+QUERY_KEYS)
    if explicit and signature!=last:
        catalogue=read_catalogue(root/'data/schedule_2026.json')
        selection,notices=decode_link(query,catalogue)
        mirror_selection(selection)
        st.session_state.update(page=VIEWS[selection['view']],site_view=selection['view'],
                                analysis_tab=selection['tab'],analysis_large=selection['large'],
                                _route_selection=selection,_route_notice=notices)
    st.session_state['_route_query']=signature


def render_navigation(root):
    try:
        restore_link(root)
    except (OSError,ValueError,TypeError,KeyError):
        # Existing page-specific loaders still display their own data errors.
        pass
    page=st.session_state.get('page','home')
    # Existing homepage handoffs set `page`; keep that established path valid.
    if st.session_state.get('_rendered_page')!=page:
        st.session_state['site_view']=next((v for v,p in VIEWS.items() if p==page),'觀賽首頁')
    with st.container(key='site_navigation'):
        st.radio('網站導覽',list(VIEWS),key='site_view',horizontal=True,
                 bind='query-params',on_change=on_nav_change,label_visibility='collapsed')
    view=st.session_state['site_view']
    st.session_state['page']=VIEWS[view]
    st.session_state['_rendered_page']=VIEWS[view]
    if st.session_state.get('_scroll_view')!=view:
        st.session_state['_scroll_view']=view
        # A destination change starts at its heading. Ordinary widget reruns
        # must leave the visitor's reading/chart position alone.
        st.html('<script>/* destination: '+VIEWS[view]+''' */
          requestAnimationFrame(() => requestAnimationFrame(() => {
            const main = document.querySelector('[data-testid="stMain"]');
            if (main) main.scrollTo({top: 0, behavior: 'instant'});
          }));
        </script>''',unsafe_allow_javascript=True)
    for notice in st.session_state.pop('_route_notice',[]):
        st.info(notice)
    return VIEWS[view]


def sync_link(root):
    catalogue=read_catalogue(root/'data/schedule_2026.json')
    selection=current_selection()
    index=selection.get('index')
    if index is None:
        index=next((i for i,e in enumerate(catalogue['events']) if e['event']=='United States Grand Prix'),0)
    index=max(0,min(int(index),len(catalogue['events'])-1))
    selection['index']=index
    st.session_state['_route_selection']=selection
    desired=dict(year='2026',event=slug(catalogue['events'][index]['event']),session=selection['code'])
    for key in ('a','b'):
        if selection.get(key):
            desired[key]=selection[key]
    if st.session_state.get('page')=='analysis':
        desired['large']='1' if st.session_state.get('analysis_large') else '0'
    current=st.query_params.to_dict()
    for key in QUERY_KEYS:
        if key not in desired and key in current:
            del st.query_params[key]
    updates={k:v for k,v in desired.items() if current.get(k)!=v}
    if updates:
        st.query_params.update(updates)
    st.session_state['_route_query']=query_signature(st.query_params.to_dict())
    public={'site_view':st.session_state.get('site_view','觀賽首頁'),**desired}
    if st.session_state.get('page')=='analysis':
        public['analysis_tab']=st.session_state.get('analysis_tab',TABS[0])
    return BASE_URL+'?'+urlencode(public)


def share_current(root):
    try:
        url=sync_link(root)
    except (OSError,ValueError,TypeError,KeyError):
        return
    with st.expander('分享這個頁面與比較選擇'):
        st.caption('複製下方連結，可在另一台電腦開啟相同分站、場次、A／B 車手、分析分頁與大字設定。額外加入的節奏車手、圈次範圍、同步查看圈次、距離放大與圖表游標不包含在連結中。')
        st.code(url,language=None)
