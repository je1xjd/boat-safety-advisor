"""
web_charts.py

StreamlitのWeb版で使用するAltairグラフの描画および数値抽出ヘルパー。
"""

import math
import re

import altair as alt
import pandas as pd

from engine import SafetyRule, get_wind_arrow


def extract_number(val: str | float) -> float:
    """文字列や数値から最初の数値を抽出する。"""
    m = re.search(r"(-?\d+(?:\.\d+)?)", str(val))
    return float(m.group(1)) if m else 0.0


def _calculate_nice_upper_limit(lim_max: float) -> float:
    """制限値の約2倍をベースに、グラフの目盛りが綺麗になるキリの良い上限値を算出する。"""
    if lim_max <= 0:
        return 10.0
    
    double_lim = lim_max * 2.0
    
    # 規模感に応じてキリの良い単位（ステップ）で切り上げる
    if double_lim <= 5:
        return math.ceil(double_lim * 2) / 2  # 0.5刻み (例: 1.6 -> 2.0)
    elif double_lim <= 20:
        return math.ceil(double_lim / 5) * 5   # 5刻み (例: 11 -> 15, 18 -> 20)
    elif double_lim <= 100:
        return math.ceil(double_lim / 10) * 10 # 10刻み
    else:
        return math.ceil(double_lim / 50) * 50 # 50刻み (例: 70×2=140 -> 150)


def draw_fixed_chart(
    df: pd.DataFrame,
    y_col: str,
    color: str,
    limit_val: float | list | str = None,
    limit_label: str = None,
    y_max: float = None,
    y_min: float = 0,
    is_lower_danger: bool = False,
) -> alt.Chart:
    """指定された条件と制限値に基づいてAltairチャートを生成する。"""
    
    data_max = df[y_col].max() if not df[y_col].empty else 0
    
    lim_max = 0
    if isinstance(limit_val, str) and limit_val in df.columns:
        lim_max = df[limit_val].max()
    elif isinstance(limit_val, (list, tuple)):
        lim_max = max(limit_val) if limit_val else 0
    elif limit_val is not None:
        lim_max = float(limit_val)

    # 制限値からキリの良い2倍のデフォルト上限を算出し、データ超過時はダイナミックに拡張
    if lim_max > 0:
        base_limit_top = _calculate_nice_upper_limit(lim_max)
        calculated_max = max(base_limit_top, data_max * 1.1)
    else:
        calculated_max = max(data_max * 1.1, 10.0)

    final_max = y_max if y_max is not None else calculated_max

    if y_min < 0:
        y_scale_args = {
            "zero": False,
            "domain": [y_min, final_max],
            "nice": False,
        }
    else:
        y_scale_args = {
            "zero": True,
            "domain": [0, final_max],
            "nice": False,
        }

    line = (
        alt.Chart(df)
        .mark_line(point=True, color=color)
        .encode(
            x=alt.X(
                "時間:Q",
                title="時間",
                scale=alt.Scale(
                    domain=[
                        SafetyRule.ACTIVITY_START_HOUR,
                        SafetyRule.ACTIVITY_END_HOUR,
                    ]
                ),
                axis=alt.Axis(
                    format="d",
                    tickCount=SafetyRule.ACTIVITY_END_HOUR
                    - SafetyRule.ACTIVITY_START_HOUR
                    + 1,
                    values=list(
                        range(
                            SafetyRule.ACTIVITY_START_HOUR,
                            SafetyRule.ACTIVITY_END_HOUR + 1,
                        )
                    ),
                ),
            ),
            y=alt.Y(f"{y_col}:Q", title=y_col, scale=alt.Scale(**y_scale_args)),
            tooltip=[
                alt.Tooltip("時間:Q", title="時間", format="d"),
                alt.Tooltip(f"{y_col}:Q", title=y_col, format=".1f"),
            ],
        )
    )

    layers = [line]

    # 風速グラフの場合、Web版向けのカラー絵文字付き風向矢印レイヤーを追加する
    if y_col in ["風速", "wind"] and "風向" in df.columns:
        df_arrow = df.copy()
        # Web版では use_emoji=True を明示してカラー絵文字の矢印を取得
        df_arrow["_arrow"] = df_arrow["風向"].apply(
            lambda x: get_wind_arrow(x, use_emoji=True) if pd.notna(x) else ""
        )
        df_arrow["_arrow_y"] = df_arrow[y_col] + 0.6

        arrow_layer = (
            alt.Chart(df_arrow)
            .mark_text(align="center", baseline="bottom", fontSize=14, color="#333333")
            .encode(
                x="時間:Q",
                y="_arrow_y:Q",
                text="_arrow:N",
                tooltip=[
                    alt.Tooltip("時間:Q", title="時間", format="d"),
                    alt.Tooltip("風向:N", title="風向"),
                ]
            )
        )
        layers.append(arrow_layer)

    if limit_val is not None:
        label_text = limit_label or "制限値"
        temp_df = df.copy()
        
        lower_danger = is_lower_danger or (y_col == "潮位")
        
        if isinstance(limit_val, str) and limit_val in temp_df.columns:
            temp_df["_limit_legend"] = label_text
            lim_series = temp_df[limit_val]
            
            limit_layer = (
                alt.Chart(temp_df)
                .mark_line(strokeDash=[4, 4], size=2)
                .encode(
                    x="時間:Q",
                    y=alt.Y(f"{limit_val}:Q", title=None),
                    color=alt.Color(
                        "_limit_legend:N",
                        scale=alt.Scale(domain=[label_text], range=["red"]),
                        legend=alt.Legend(
                            title=None, orient="top-right", symbolType="stroke"
                        ),
                    ),
                    tooltip=[alt.Tooltip(f"{limit_val}:Q", title=label_text, format=".1f")]
                )
            )
            layers.append(limit_layer)
            
        elif isinstance(limit_val, (list, tuple)):
            temp_df["_dynamic_limit"] = list(limit_val)
            temp_df["_limit_legend"] = label_text
            lim_series = temp_df["_dynamic_limit"]
            
            limit_layer = (
                alt.Chart(temp_df)
                .mark_line(strokeDash=[4, 4], size=2)
                .encode(
                    x="時間:Q",
                    y=alt.Y("_dynamic_limit:Q", title=None),
                    color=alt.Color(
                        "_limit_legend:N",
                        scale=alt.Scale(domain=[label_text], range=["red"]),
                        legend=alt.Legend(
                            title=None, orient="top-right", symbolType="stroke"
                        ),
                    ),
                )
            )
            layers.append(limit_layer)
        else:
            lim_series = float(limit_val)
            rule_df = pd.DataFrame([{"y_val": lim_series, "legend_label": label_text}])
            
            limit_layer = (
                alt.Chart(rule_df)
                .mark_rule(color="red", strokeDash=[4, 4], size=2)
                .encode(
                    y="y_val:Q",
                    strokeDash=alt.value([4, 4]),
                    color=alt.Color(
                        "legend_label:N",
                        scale=alt.Scale(domain=[label_text], range=["red"]),
                        legend=alt.Legend(
                            title=None, orient="top-right", symbolType="stroke"
                        ),
                    ),
                )
            )
            layers.append(limit_layer)

        if lower_danger:
            danger_mask = temp_df[y_col] < lim_series
        else:
            danger_mask = temp_df[y_col] > lim_series
            
        danger_df = temp_df[danger_mask].copy()
        
        if not danger_df.empty:
            danger_points = (
                alt.Chart(danger_df)
                .mark_text(text="✖", color="red", size=22, baseline="middle", align="center")
                .encode(
                    x="時間:Q",
                    y=alt.Y(f"{y_col}:Q"),
                    tooltip=[
                        alt.Tooltip("時間:Q", title="時間", format="d"),
                        alt.Tooltip(f"{y_col}:Q", title=y_col, format=".1f"),
                    ]
                )
            )
            layers.append(danger_points)

    chart = alt.layer(*layers).properties(height=300)

    return chart.configure_axis(
        grid=True, gridColor="#E0E0E0", gridDash=[2, 2], gridWidth=0.5
    )


def draw_precip_temp_chart(df: pd.DataFrame) -> alt.Chart:
    """
    左軸：降水確率（棒グラフ / 0〜100%）
    右軸：気温（折れ線グラフ / ℃）
    を組み合わせた2軸複合グラフを生成する。
    """
    x_enc = alt.X(
        "時間:Q",
        title="時間",
        scale=alt.Scale(
            domain=[SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR]
        ),
        axis=alt.Axis(
            format="d",
            tickCount=SafetyRule.ACTIVITY_END_HOUR - SafetyRule.ACTIVITY_START_HOUR + 1,
            values=list(
                range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1)
            ),
        ),
    )

    bars = (
        alt.Chart(df)
        .mark_bar(color="#4682b4", opacity=0.55, width=18)
        .encode(
            x=x_enc,
            y=alt.Y(
                "降水確率:Q",
                title="降水確率 (%)",
                scale=alt.Scale(domain=[0, 100], zero=True),
                axis=alt.Axis(grid=True, gridColor="#E0E0E0"),
            ),
            tooltip=[
                alt.Tooltip("時間:Q", title="時間", format="d"),
                alt.Tooltip("降水確率:Q", title="降水確率", format=".0f"),
            ],
        )
    )

    temp_min = df["気温"].min() if not df.empty else 0
    temp_max = df["気温"].max() if not df.empty else 30

    lines = (
        alt.Chart(df)
        .mark_line(
            color="#ff4500",
            strokeWidth=2.5,
            point=alt.OverlayMarkDef(color="#ff4500", size=60),
        )
        .encode(
            x=x_enc,
            y=alt.Y(
                "気温:Q",
                title="気温 (℃)",
                scale=alt.Scale(
                    domain=[max(0, temp_min - 3), temp_max + 3], zero=False
                ),
                axis=alt.Axis(
                    orient="right",
                    grid=False,
                    labelColor="#ff4500",
                    titleColor="#ff4500",
                ),
            ),
            tooltip=[
                alt.Tooltip("時間:Q", title="時間", format="d"),
                alt.Tooltip("気温:Q", title="気温", format=".1f"),
            ],
        )
    )

    chart = (
        alt.layer(bars, lines)
        .resolve_scale(y="independent")
        .properties(height=320)
        .configure_axis(gridDash=[2, 2], gridWidth=0.5)
    )

    return chart
