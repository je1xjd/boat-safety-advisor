"""
charts.py

StreamlitのWeb版で使用するAltairグラフの描画および数値抽出ヘルパー。
"""

import re
import pandas as pd
import altair as alt
from engine import SafetyRule


def extract_number(val: str | float | int) -> float:
    """文字列や数値から最初の数値（小数含む）を抽出する。"""
    m = re.search(r"(\d+\.?\d*)", str(val))
    return float(m.group(1)) if m else 0.0


def draw_fixed_chart(
    df: pd.DataFrame, 
    y_col: str, 
    color: str, 
    limit_val: float = None, 
    limit_label: str = None, 
    y_max: float = None
) -> alt.Chart:
    """指定された条件と制限値に基づいて固定スケールのAltairチャートを生成する。"""
    y_scale_args = {"zero": True}
    if y_max is not None:
        y_scale_args["domain"] = [0, y_max]

    line = alt.Chart(df).mark_line(point=True, color=color).encode(
        x=alt.X("時間:Q", 
                title="時刻", 
                scale=alt.Scale(domain=[SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR]),
                axis=alt.Axis(
                    format="d", 
                    tickCount=SafetyRule.ACTIVITY_END_HOUR - SafetyRule.ACTIVITY_START_HOUR + 1,
                    values=list(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
                )
        ), 
        y=alt.Y(f"{y_col}:Q", title=y_col, scale=alt.Scale(**y_scale_args))
    )

    if limit_val is not None:
        label_text = limit_label or "制限値"
        rule_df = pd.DataFrame([{
            "y_val": limit_val,
            "legend_label": label_text
        }])
        rule = alt.Chart(rule_df).mark_rule(
            color="red",
            strokeDash=[4, 4],
            size=2
        ).encode(
            y="y_val:Q",
            strokeDash=alt.value([4, 4]),
            color=alt.Color(
                "legend_label:N", 
                scale=alt.Scale(domain=[label_text], range=["red"]), 
                legend=alt.Legend(
                    title=None, 
                    orient="top-right",
                    symbolType="stroke"
                )
            )
        )
        chart = alt.layer(line, rule).properties(height=300)
    else:
        chart = line.properties(height=300)

    return chart.configure_axis(
        grid=True,
        gridColor="#E0E0E0",
        gridDash=[2, 2],
        gridWidth=0.5
    )
