"""Shared plot styling; A/B colours stay consistent between analysis views."""
PALETTE = ("#50cce5", "#ff786c", "#e8c76c", "#b4a1fa")


def style_chart(figure, axes):
    figure.set_facecolor("#12171f")
    for axis in axes:
        axis.set_facecolor("#12171f")
        axis.tick_params(colors="#aeb8c8", labelsize=10)
        axis.xaxis.label.set_color("#cbd3df")
        axis.yaxis.label.set_color("#cbd3df")
        axis.title.set_color("#edf1f6")
        for spine in axis.spines.values():
            spine.set_color("#354050")
