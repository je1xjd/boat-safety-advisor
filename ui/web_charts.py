"""
web_charts.py

StreamlitのWeb版で使用するAltairグラフの描画および数値抽出ヘルパー。
"""

import re

import altair as alt
import pandas as pd

from engine import SafetyRule


def extract_number(val: str | float) -> float:
    """文字列や数値から最初の数値を抽出する。"""
    m = re.search(r"(-?\d+(?:\.\d+)?)", str(val))
    return float(m.group(1)) if m else 0.0


def draw_fixed_chart(
    df: pd.DataFrame,
    y_col: str,
    color: str,
    limit_val: float | list | str = None,  # 数値だけでなくリストや列名も許容
    limit_label: str = None,
    y_max: float = None,
    y_min: float = 0,  # デフォルトを0に設定（風・波は0固定）
    is_lower_danger: bool = False, # 潮位などのように下回ると危険な場合はTrue
) -> alt.Chart:
    """指定された条件と制限値（固定値または動的配列/列）に基づいてAltairチャートを生成する。"""
    
    # --- 💡 動的なY軸ドメイン（上限・下限）の算出 ---
    data_max = df[y_col].max() if not df[y_col].empty else 0
    
    # 制限値の最大値を取得
    lim_max = 0
    if isinstance(limit_val, str) and limit_val in df.columns:
        lim_max = df[limit_val].max()
    elif isinstance(limit_val, (list, tuple)):
        lim_max = max(limit_val) if limit_val else 0
    elif limit_val is not None:
        lim_max = float(limit_val)

    # 1. 制限値がある場合は「制限値の2倍」をベース上限とする（常に真ん中付近に制限値が来るようにする）
    # 2. 予測データ(data_max)がそれを超えて大きくなっている場合は、データに合わせてさらに拡張する
    if lim_max > 0:
        calculated_max = max(lim_max * 2.0, data_max * 1.1)
    else:
        # 制限値がない一般的な項目の場合
        calculated_max = max(data_max * 1.1, 10.0)

    final_max = y_max if y_max is not None else calculated_max

    # 💡 y_min がマイナス（潮位など）の場合は zero=False にし、マイナス側の指定を有効にする
    if y_min < 0:
        y_scale_args = {
            "zero": False,
            "domain": [y_min, final_max],
            "nice": False,
        }
    else:
        # 風や波などのように下限が0の場合（"nice": False で勝手に上限が広がるのを防ぐ）
        y_scale_args = {
            "zero": True,
            "domain": [0, final_max],
            "nice": False,
        }

    # 基本の折れ線グラフレイヤー
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

    if limit_val is not None:
        label_text = limit_label or "制限値"
        temp_df = df.copy()
        
        # 危険側の判定（潮位は下回った場合、それ以外は上回った場合）
        # ※呼び出し元で is_lower_danger が指定されていない場合も考慮して "潮位" という文字列でフォールバック判定
        lower_danger = is_lower_danger or (y_col == "潮位")
        
        # 💡 limit_val の型に応じた制限値ラインの作成と、比較用Seriesの取得
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

        # --- 危険ポイント（制限値超過）の「✖」マーク描画 ---
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

    # 用意したレイヤーをすべて重ね合わせる
    chart = alt.layer(*layers).properties(height=300)

    return chart.configure_axis(
        grid=True, gridColor="#E0E0E0", gridDash=[2, 2], gridWidth=0.5
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

    # 左軸：降水確率（棒グラフ）
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

    # 右軸：気温（折れ線グラフ）
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

    # レイヤー結合（背景なし、独立したY軸スケールを適用）
    chart = (
        alt.layer(bars, lines)
        .resolve_scale(y="independent")
        .properties(height=320)
        .configure_axis(gridDash=[2, 2], gridWidth=0.5)
    )

    return chart
