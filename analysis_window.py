"""Distance windows operate on an already aligned lap; never re-zero delta."""
import numpy as np
import streamlit as st


def preset_window(maximum, part=None):
    if part is None:
        return (0, maximum)
    return (int(maximum * part / 3), int(maximum * (part + 1) / 3))


def set_window(maximum, part=None):
    st.session_state['telemetry_window'] = preset_window(maximum, part)


def distance_controls(identity, maximum):
    if st.session_state.get('telemetry_window_identity') != identity:
        st.session_state['telemetry_window_identity'] = identity
        st.session_state['telemetry_window'] = (0, maximum)
    with st.expander('距離區段與放大'):
        presets = st.container(key='window_presets')
        for column, label, part in zip(presets.columns(4), ['整圈', '前 1/3', '中 1/3', '後 1/3'], [None, 0, 1, 2]):
            column.button(label, on_click=set_window, args=(maximum, part), key=f'window_part_{part}', width='stretch')
        selected = st.slider('A 車手圈內距離（公尺）', 0, maximum, key='telemetry_window', step=1)
        st.caption('拖動兩端放大區段；也可用鍵盤方向鍵調整。時間差保留整圈累積值，不會從區段起點歸零。')
    return selected


def window_observation(samples, lower, upper, a_code, b_code):
    first, last = float(samples.distance.iloc[0]), float(samples.distance.iloc[-1])
    low, high = max(lower, first), min(upper, last)
    if high <= low:
        return None
    start, end = np.interp([low, high], samples.distance, samples.delta)
    movement = float(end - start)
    direction = '變化小於 0.001 秒' if abs(movement) < .0005 else f'向 {a_code if movement > 0 else b_code} 方向變化 {abs(movement):.3f} 秒'
    return {'lower':low, 'upper':high, 'start':float(start), 'end':float(end),
            'movement':movement, 'text':f'在 {low:,.0f}–{high:,.0f} 公尺，時間差由 {start:+.3f} 變為 {end:+.3f} 秒，{direction}。'}
