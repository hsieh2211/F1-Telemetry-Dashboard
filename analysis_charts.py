"""Responsive offline Vega charts; tooltips retain source values and reasons."""
import altair as alt


def _theme(chart):
    return (chart.properties(background="#12171f", padding={"top": 12, "bottom": 12, "left": 8, "right": 8})
            .configure_view(stroke=None)
            .configure_axis(labelColor="#b8c3d2", titleColor="#cbd3df", gridColor="#263140",
                            domainColor="#354050", labelFontSize=12, titleFontSize=13,
                            titleFontWeight="normal", labelPadding=7, titlePadding=12)
            .configure_legend(labelColor="#dbe2ec", labelFontSize=12, symbolStrokeWidth=3))


def pace_charts(annotated, chosen, colours, lower, upper):
    records = annotated.copy()
    # Segment lines at excluded/missing laps rather than joining across gaps.
    records["segment"] = records.groupby("driver", sort=False)["included"].transform(lambda s: (~s).cumsum())
    records["gap"] = records.groupby("driver", sort=False)["lap"].transform(lambda s: s.diff().gt(1).cumsum())
    records["segment_id"] = records["segment"].astype(str) + ":" + records["gap"].astype(str)
    scale = alt.Scale(domain=chosen, range=[colours[c] for c in chosen])
    x = alt.X("lap:Q", title="比賽圈次", scale=alt.Scale(domain=[lower - .5, upper + .5]),
              axis=alt.Axis(tickMinStep=1, format="d", tickCount=min(8, upper - lower + 1)))
    tooltips = [alt.Tooltip("driver:N", title="車手"), alt.Tooltip("lap:Q", title="圈次", format=".0f"),
                alt.Tooltip("lap_seconds:Q", title="圈速（秒）", format=".3f"),
                alt.Tooltip("compound:N", title="胎種"), alt.Tooltip("tyre_life:Q", title="胎齡", format=".0f")]
    curve = (alt.Chart(records[records["included"]]).mark_line(strokeWidth=2, point={"filled": True, "size": 28})
             .encode(x=x, y=alt.Y("lap_seconds:Q", title="圈速（秒）", scale=alt.Scale(zero=False)),
                     color=alt.Color("driver:N", scale=scale, title=None,
                                     legend=alt.Legend(orient="top", direction="horizontal", columns=4)),
                     detail=["driver:N", "segment_id:N"], order="lap:Q", tooltip=tooltips)
             .properties(height=280, description="所選車手的有效逐圈圈速；排除的圈與資料缺口保留斷點。"))
    excluded = (alt.Chart(records[~records["included"]]).mark_point(shape="cross", angle=45, size=45, strokeWidth=1.5)
                .encode(x=x, y=alt.Y("driver:N", title="未採用", sort=chosen, axis=alt.Axis(labelAngle=0)),
                        color=alt.Color("driver:N", scale=scale, legend=None),
                        tooltip=tooltips + [alt.Tooltip("excluded_reason:N", title="排除原因")])
                .properties(height=max(140, len(chosen) * 28 + 70), description="未納入節奏的圈；點選或懸停標記查看排除原因。"))
    return _theme(curve), _theme(excluded)


def tyre_chart(selected, chosen, tyres, lower, upper):
    records = selected.copy()
    records["start"] = records["lap"] - .42
    records["end"] = records["lap"] + .42
    records["tyre_label"] = records["compound"].map({k: v[0] for k, v in tyres.items()}).fillna("未提供")
    chart = (alt.Chart(records).mark_rect(cornerRadius=2)
             .encode(x=alt.X("start:Q", title="比賽圈次", scale=alt.Scale(domain=[lower - .5, upper + .5]),
                            axis=alt.Axis(tickMinStep=1, format="d", tickCount=min(8, upper - lower + 1))),
                     x2="end:Q", y=alt.Y("driver:N", title=None, sort=chosen, scale=alt.Scale(paddingInner=.4)),
                     color=alt.Color("tyre_label:N", title=None, legend=alt.Legend(orient="top", columns=3),
                                     scale=alt.Scale(domain=[v[0] for v in tyres.values()] + ["未提供"],
                                                     range=[v[1] for v in tyres.values()] + ["#888888"])),
                     tooltip=[alt.Tooltip("driver:N", title="車手"), alt.Tooltip("lap:Q", title="圈次", format=".0f"),
                              alt.Tooltip("tyre_label:N", title="胎種"), alt.Tooltip("compound:N", title="原始胎種"),
                              alt.Tooltip("stint:Q", title="輪胎段", format=".0f"), alt.Tooltip("tyre_life:Q", title="胎齡", format=".0f")])
             .properties(height=max(210, len(chosen) * 38 + 110), description="所選範圍內逐圈輪胎使用紀錄，缺少胎種以灰色顯示。"))
    return _theme(chart)
