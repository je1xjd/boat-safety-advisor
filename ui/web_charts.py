"""
web_charts.py

StreamlitのWeb版で使用するAltairグラフの描画および数値抽出ヘルパー。
"""

import re
import pandas as pd
import altair as alt
from engine import SafetyRule, StatusFormatter


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
    """指定された条件と制限値に基づいて固定スケールの単一項目のAltairチャートを生成する。"""
    y_scale_args = {"zero": True}
    if y_max is not None:
        y_scale_args["domain"] = [0, y_max]

    line = alt.Chart(df).mark_line(point=True, color=color).encode(
        x=alt.X(
            "時間:Q", 
            title="時刻", 
            scale=alt.Scale(domain=[SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR]),
            axis=alt.Axis(
                format="d", 
                tickCount=SafetyRule.ACTIVITY_END_HOUR - SafetyRule.ACTIVITY_START_HOUR + 1,
                values=list(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
            )
        ),
        y=alt.Y(f"{y_col}:Q", title=y_col, scale=alt.Scale(**y_scale_args)),
        tooltip=[
            alt.Tooltip("時間:Q", title="時刻", format="d"),
            alt.Tooltip(f"{y_col}:Q", title=y_col, format=".1f")
        ]
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


def draw_precip_temp_chart(df: pd.DataFrame) -> alt.Chart:
    """
    左軸：降水確率（棒グラフ / 0〜100%）
    右軸：気温（折れ線グラフ / ℃）
    を組み合わせた2軸複合グラフを生成する（背景色はなし）。
    """
    # 共通のX軸設定
    x_enc = alt.X(
        "時間:Q", 
        title="時刻", 
        scale=alt.Scale(domain=[SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR]),
        axis=alt.Axis(
            format="d", 
            tickCount=SafetyRule.ACTIVITY_END_HOUR - SafetyRule.ACTIVITY_START_HOUR + 1,
            values=list(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
        )
    )

    # 左軸：降水確率（棒グラフ）
    bars = alt.Chart(df).mark_bar(
        color="#4682b4", 
        opacity=0.55, 
        width=18
    ).encode(
        x=x_enc,
        y=alt.Y(
            "降水確率:Q", 
            title="降水確率 (%)", 
            scale=alt.Scale(domain=[0, 100], zero=True),
            axis=alt.Axis(grid=True, gridColor="#E0E0E0")
        ),
        tooltip=[
            alt.Tooltip("時間:Q", title="時刻", format="d"),
            alt.Tooltip("降水確率:Q", title="降水確率", format=".0f"),
            alt.Tooltip("判定:N", title="判定")
        ]
    )

    # 右軸：気温（折れ線グラフ）
    temp_min = df["気温"].min() if not df.empty else 0
    temp_max = df["気温"].max() if not df.empty else 30
    
    lines = alt.Chart(df).mark_line(
        color="#ff4500", 
        strokeWidth=2.5,
        point=alt.OverlayMarkDef(color="#ff4500", size=60)
    ).encode(
        x=x_enc,
        y=alt.Y(
            "気温:Q", 
            title="気温 (℃)", 
            scale=alt.Scale(domain=[max(0, temp_min - 3), temp_max + 3], zero=False),
            axis=alt.Axis(
                orient="right", 
                grid=False,
                labelColor="#ff4500",
                titleColor="#ff4500"
            )
        ),
        tooltip=[
            alt.Tooltip("時間:Q", title="時刻", format="d"),
            alt.Tooltip("気温:Q", title="気温", format=".1f"),
            alt.Tooltip("判定:N", title="判定")
        ]
    )

    # レイヤー結合（背景なし、独立したY軸スケールを適用）
    chart = alt.layer(bars, lines).resolve_scale(
        y='independent'
    ).properties(
        height=320
    ).configure_axis(
        gridDash=[2, 2],
        gridWidth=0.5
    )

    return chart
