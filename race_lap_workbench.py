"""Linked lap inspection, preserving source gaps and pace quality decisions."""
import altair as alt
import pandas as pd
import streamlit as st
from analysis_charts import pace_charts, tyre_chart, _theme


def bounded_lap(value, lower, upper):
    try:
        number=float(value)
        return max(lower,min(upper,int(number))) if number.is_integer() else lower
    except (ValueError,TypeError,OverflowError):
        return lower


def selected_rows(annotated, chosen, lap):
    """Keep a row for missing drivers; never substitute a nearby lap."""
    result=[]
    for driver in chosen:
        rows=annotated[(annotated.driver==driver)&(annotated.lap==lap)]
        result.append((driver,None if rows.empty else rows.iloc[0].to_dict()))
    return result


def linked_chart(annotated, chosen, colours, tyres, lower, upper, focus):
    curve,excluded=pace_charts(annotated,chosen,colours,lower,upper)
    tyre=tyre_chart(annotated,chosen,tyres,lower,upper)
    pick=alt.selection_point(name='lap_pick',fields=['lap'],on='click',clear=False,toggle=False)
    panels=[]
    for chart,title in ((curve,'有效逐圈圈速'),(excluded,'未納入節奏的圈'),(tyre,'逐圈輪胎使用')):
        chart=chart.copy(deep=True)
        chart.config=alt.Undefined
        chart.background=alt.Undefined
        chart.padding=alt.Undefined
        scale=alt.Scale(domain=[lower-.5,upper+.5],nice=False,zero=False)
        chart.encoding.x.scale=scale
        marker=alt.Chart(pd.DataFrame({'focus':[focus]})).mark_rule(color='#f5f8fc',strokeDash=[5,4],strokeWidth=1.5).encode(x=alt.X('focus:Q',scale=scale))
        panel=alt.layer(chart.add_params(pick),marker).properties(title=title,width='container')
        panels.append(_theme(panel).configure_axisY(minExtent=36,maxExtent=36).properties(
            autosize=alt.AutoSizeParams(type='fit-x',contains='padding',resize=True)))
    return panels


def accept_chart_lap(chart_key, focus_key, lower, upper):
    points=st.session_state.get(chart_key,{}).get('selection',{}).get('lap_pick',[])
    if points:
        st.session_state[focus_key]=bounded_lap(points[-1].get('lap'),lower,upper)


def show_lap_details(annotated, chosen, focus, tyres):
    with st.container(border=True,key='pace_lap_details'):
        st.markdown(f'### 第 {focus} 圈 · 同步查看')
        st.caption('對齊同一比賽圈次；不代表各車在同一時刻或同一賽道位置。')
        rows=selected_rows(annotated,chosen,focus)
        for start in range(0,len(rows),2):
            for column,(driver,row) in zip(st.columns(min(2,len(rows)-start)),rows[start:start+2]):
                with column:
                    st.markdown(f'**{driver} · 第 {focus} 圈**')
                    if row is None:
                        st.info('此圈未提供紀錄，不以其他圈補值。')
                        continue
                    def number(field,suffix='',digits=0):
                        value=row.get(field)
                        return '未提供' if pd.isna(value) else f'{value:.{digits}f}{suffix}'
                    st.write('圈速：'+number('lap_seconds',' 秒',3))
                    compound=row.get('compound')
                    st.write('輪胎：'+tyres.get(compound,('未提供',))[0]+' · 胎齡 '+number('tyre_life',' 圈'))
                    st.caption('輪胎段：'+number('stint'))
                    if row['included']:
                        st.caption('已納入有效圈節奏')
                    else:
                        st.write('未納入節奏：'+row['excluded_reason'])
                    events=[]
                    for field,label in (('pit_in_seconds','進站'),('pit_out_seconds','出站')):
                        if pd.notna(row.get(field)):
                            events.append(label+' '+number(field,' 秒',3))
                    st.write('進出站：'+('；'.join(events) if events else '此圈未記錄時間'))
        st.caption('進出站時間沿用場次計時原點，可能跨圈；不是停車換胎秒數，也不是進站損失。')


@st.fragment
def render_lap_workbench(annotated, chosen, colours, tyres, lower, upper, identity):
    suffix='_'.join(map(str,identity))
    focus_key='pace_focus_'+suffix
    st.session_state[focus_key]=bounded_lap(st.session_state.get(focus_key,lower),lower,upper)
    focus=st.selectbox('同步查看圈次',range(lower,upper+1),key=focus_key,format_func=lambda n:f'第 {n} 圈')
    st.caption('點選圈速點、排除標記或輪胎格，可同步更新圈次；手機與鍵盤也可使用上方選單。白色虛線標示目前圈次。')
    chart_key='pace_linked_'+suffix+'_'+'_'.join(chosen)+f'_{lower}_{upper}'
    for index,chart in enumerate(linked_chart(annotated,chosen,colours,tyres,lower,upper,focus)):
        key=chart_key+'_'+str(index)
        st.altair_chart(chart,width='stretch',theme=None,key=key,selection_mode='lap_pick',
                        on_select=lambda key=key:accept_chart_lap(key,focus_key,lower,upper))
    show_lap_details(annotated,chosen,focus,tyres)
