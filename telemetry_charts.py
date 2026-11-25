"""Offline lap comparison with a shared distance probe and explicit alignment."""
import altair as alt
import numpy as np
import pandas as pd
from analysis_charts import _theme
from analysis_theme import PALETTE


def aligned_samples(reference, comparison, delta):
    """Probe on A's original grid; B is interpolated by relative lap progress.

    Brake is a discrete signal: take the preceding B sample, never interpolate it.
    Original exports remain unchanged and downloadable separately.
    """
    a, b = reference, comparison
    ad, bd = a.Distance.to_numpy(), b.Distance.to_numpy()
    ap = (ad - ad[0]) / (ad[-1] - ad[0])
    bp = (bd - bd[0]) / (bd[-1] - bd[0])
    result = pd.DataFrame({"distance": ad, "delta": delta})
    for key in ("Speed", "Throttle"):
        result[f"a_{key}"] = a[key].to_numpy()
        result[f"b_{key}"] = np.interp(ap, bp, b[key])
    result["a_Brake"] = a.Brake.to_numpy()
    prior = np.clip(np.searchsorted(bp, ap, side="right") - 1, 0, len(b) - 1)
    result["b_Brake"] = b.Brake.to_numpy()[prior]
    return result


def telemetry_chart(reference, comparison, delta, a_code, b_code, view="重點檢視"):
    data = aligned_samples(reference, comparison, delta)
    colours = alt.Scale(domain=[a_code, b_code], range=list(PALETTE[:2]))
    probe = alt.selection_point(name="lap_probe", fields=["distance"], nearest=True,
                                on="pointermove, click", clear="dblclick", empty=False)
    x = alt.X("distance:Q", title="A 車手圈內距離（公尺）", axis=alt.Axis(tickCount=5, format=",.0f"))
    tips = [alt.Tooltip("distance:Q", title="A 圈內距離（公尺）", format=".0f"),
            alt.Tooltip("a_Speed:Q", title=f"{a_code} 速度", format=".1f"),
            alt.Tooltip("b_Speed:Q", title=f"{b_code} 速度（對齊估計）", format=".1f"),
            alt.Tooltip("delta:Q", title="時間差（秒）", format="+.3f"),
            alt.Tooltip("a_Throttle:Q", title=f"{a_code} 油門 %", format=".0f"),
            alt.Tooltip("b_Throttle:Q", title=f"{b_code} 油門 %（對齊估計）", format=".0f"),
            alt.Tooltip("a_Brake:Q", title=f"{a_code} 煞車 0／1", format=".0f"),
            alt.Tooltip("b_Brake:Q", title=f"{b_code} 煞車 0／1（前筆）", format=".0f")]
    base = alt.Chart(data).encode(x=x)

    def signal(key, title, height, stepped=False):
        chart = (base.transform_fold([f"a_{key}", f"b_{key}"], as_=["series", "value"])
                 .transform_calculate(driver=f"datum.series === 'a_{key}' ? '{a_code}' : '{b_code}'")
                 .mark_line(strokeWidth=2, interpolate="step-after" if stepped else "linear")
                 .encode(y=alt.Y("value:Q", title=title, scale=alt.Scale(zero=key != "Speed"), axis=alt.Axis(values=[0,1]) if stepped else alt.Axis()),
                         color=alt.Color("driver:N", title=None, scale=colours, legend=None),
                         strokeDash=alt.StrokeDash("driver:N", scale=alt.Scale(domain=[a_code,b_code],range=[[1,0],[6,3]]),legend=None)))
        rule = base.transform_filter(probe).mark_rule(color="#e1e8f1",strokeDash=[3,3]).encode(tooltip=tips)
        return (chart + rule).properties(height=height)

    speed = signal("Speed", "速度（km/h）", 250)
    targets = base.mark_point(opacity=0, size=120).encode(y="a_Speed:Q", tooltip=tips).add_params(probe)
    speed = speed + targets
    zero = alt.Chart(pd.DataFrame({"zero":[0]})).mark_rule(color="#8794a7",strokeDash=[4,4]).encode(y="zero:Q")
    positive = base.transform_calculate(positive="max(0, datum.delta)").mark_area(opacity=.2, color=PALETTE[0]).encode(y=alt.Y("positive:Q",title="時間差（秒）"))
    negative = base.transform_calculate(negative="min(0, datum.delta)").mark_area(opacity=.2, color=PALETTE[1]).encode(y=alt.Y("negative:Q",title="時間差（秒）"))
    line = base.mark_line(color="#e1e8f1",strokeWidth=1.5).encode(y="delta:Q")
    cursor = base.transform_filter(probe).mark_rule(color="#e1e8f1",strokeDash=[3,3]).encode(tooltip=tips)
    difference = (positive + negative + line + zero + cursor).properties(height=140)
    charts = [speed, difference]
    if view in ("完整訊號", "油門訊號"):
        charts.append(signal("Throttle", "油門（%）", 120))
    if view in ("完整訊號", "煞車訊號"):
        charts.append(signal("Brake", "煞車（0／1）", 85, stepped=True))
    chart = alt.vconcat(*charts, spacing=16).resolve_scale(x="shared", color="shared")
    return _theme(chart).properties(description="兩個個人最快圈的近似對齊比較；在速度圖點選位置，可查看各訊號。")
