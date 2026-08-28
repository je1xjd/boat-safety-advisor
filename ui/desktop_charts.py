"""
desktop_charts.py

Tkinterアプリケーション（Matplotlib）で使用する海況グラフの描画ヘルパー。
初回起動時にFigureとCanvasを初期化し、更新時は再利用する。
エンジン側で算出・保持された制限値（limit_wind, limit_wave）をそのまま活用する。
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from engine import SafetyRule


# モジュールロード時に1回だけフォントを設定
plt.rcParams["font.family"] = "Yu Gothic"

# モジュールレベルのキャッシュ
_chart_cache = {}


def dispose_desktop_graphs():
    """アプリケーション終了時にFigure・Canvasを安全に破棄する。"""
    for graph in _chart_cache.values():
        try:
            graph["canvas"].get_tk_widget().destroy()
        except Exception:
            pass

        try:
            plt.close(graph["fig"])
        except Exception:
            pass

    _chart_cache.clear()


def render_all_desktop_graphs(
    wind_tab,
    wave_tab,
    tide_tab,
    precip_tab,
    hour_data,
):
    """
    風速・波高・潮位・降水気温のグラフを指定されたタブ内に一括描画する。
    """
    filtered_items = {
        k: v
        for k, v in hour_data.items()
        if (
            SafetyRule.ACTIVITY_START_HOUR
            <= int(k)
            <= SafetyRule.ACTIVITY_END_HOUR
        )
    }

    hours = [
        int(k)
        for k in filtered_items
    ]

    winds = [
        v.wind_speed
        for v in filtered_items.values()
    ]

    waves = [
        v.wave_height
        for v in filtered_items.values()
    ]

    tides = [
        float(v.tide)
        for v in filtered_items.values()
    ]

    precips = [
        getattr(
            v,
            "precipitation_probability",
            0,
        )
        for v in filtered_items.values()
    ]

    temps = [
        getattr(v, "temperature", 0)
        for v in filtered_items.values()
    ]

    # --- 1. 風速グラフ ---
    wind_limits = [
        v.limit_wind
        for v in filtered_items.values()
    ]
    # 制限値の最大値を基に上限を動的計算（下限は0固定）
    wind_limit_max = max(wind_limits) if wind_limits else SafetyRule.WIND_LIMIT_NORMAL
    wind_data_max = max(winds) if winds else 0
    wind_dynamic_top = max(wind_limit_max * 2.0, wind_data_max * 1.1)

    _update_or_create_single_chart(
        wind_tab,
        "wind",
        hours,
        winds,
        ylabel="風速(m/s)",
        color=SafetyRule.WIND_COLOR,
        y_lim=wind_dynamic_top,
        threshold=wind_limits,
        threshold_label="制限風速",
        y_min=0,
    )

    # --- 2. 波高グラフ ---
    wave_limits = [
        v.limit_wave
        for v in filtered_items.values()
    ]
    # 制限値の最大値を基に上限を動的計算（下限は0固定）
    wave_limit_max = max(wave_limits) if wave_limits else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
    wave_data_max = max(waves) if waves else 0
    wave_dynamic_top = max(wave_limit_max * 2.0, wave_data_max * 1.1)

    _update_or_create_single_chart(
        wave_tab,
        "wave",
        hours,
        waves,
        ylabel="波高(m)",
        color=SafetyRule.WAVE_COLOR,
        y_lim=wave_dynamic_top,
        threshold=wave_limits,
        threshold_label="制限波高",
        y_min=0,
    )

    # --- 3. 潮位グラフ ---
    # マイナス潮位にも対応できるよう下限を動的に設定（既存の仕様を維持）
    tide_min = min(tides) if tides else 0
    tide_max = max(tides) if tides else 0

    tide_ylim_bottom = (
        min(-10, tide_min - 5)
        if tide_min < 0
        else 0
    )
    tide_ylim_top = max(SafetyRule.TIDE_Y_LIMIT, tide_max * 1.1)

    _update_or_create_single_chart(
        tide_tab,
        "tide",
        hours,
        tides,
        ylabel="潮位(cm)",
        color=SafetyRule.TIDE_COLOR,
        y_lim=tide_ylim_top,
        threshold=SafetyRule.MIN_TIDE_CM,
        threshold_label="最低潮位",
        y_min=tide_ylim_bottom,
    )

    # --- 4. 降水・気温グラフ ---
    _update_or_create_dual_chart(
        precip_tab,
        "precip_temp",
        hours,
        precips,
        temps,
    )


def _update_or_create_single_chart(
    parent,
    key,
    hours,
    data,
    ylabel,
    color,
    y_lim,
    threshold=None,
    threshold_label=None,
    y_min=0,
):
    """単一軸グラフを初回作成または再利用して描画する。"""
    if (
        key not in _chart_cache
        or _chart_cache[key]["parent"] != parent
    ):
        fig, ax = plt.subplots(
            figsize=(6, 4),
            dpi=100,
        )

        canvas = FigureCanvasTkAgg(
            fig,
            master=parent,
        )

        canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
        )

        _chart_cache[key] = {
            "fig": fig,
            "ax": ax,
            "canvas": canvas,
            "parent": parent,
        }
    else:
        fig = _chart_cache[key]["fig"]
        ax = _chart_cache[key]["ax"]
        canvas = _chart_cache[key]["canvas"]

    ax.clear()

    # 実測・予報データ
    ax.plot(
        hours,
        data,
        color=color,
        marker="o",
    )

    # 制限値
    if threshold is not None:
        if isinstance(threshold, (list, tuple)):
            # 時間ごとに異なる制限値
            ax.plot(
                hours,
                threshold,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=threshold_label,
            )
        else:
            # 固定の制限値
            ax.axhline(
                y=threshold,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=threshold_label,
            )

        if threshold_label:
            ax.legend(
                loc="upper right",
                fontsize=9,
            )

    ax.set_xlabel("時間")
    ax.set_ylabel(ylabel)

    ax.set_xlim(
        SafetyRule.ACTIVITY_START_HOUR,
        SafetyRule.ACTIVITY_END_HOUR,
    )

    ax.set_xticks(
        range(
            SafetyRule.ACTIVITY_START_HOUR,
            SafetyRule.ACTIVITY_END_HOUR + 1,
        )
    )

    ax.set_ylim(
        y_min,
        y_lim,
    )

    ax.grid(
        True,
        linestyle="--",
        color="#DDDDDD",
        linewidth=0.5,
        axis="both",
    )

    ax.set_axisbelow(True)

    fig.subplots_adjust(
        left=0.15,
        bottom=0.2,
        right=0.95,
        top=0.9,
    )

    canvas.draw()


def _update_or_create_dual_chart(
    parent,
    key,
    hours,
    precips,
    temps,
):
    """降水・気温の2軸グラフを初回作成または再利用して描画する。"""
    if (
        key not in _chart_cache
        or _chart_cache[key]["parent"] != parent
    ):
        fig, ax1 = plt.subplots(
            figsize=(6, 4),
            dpi=100,
        )

        ax2 = ax1.twinx()

        canvas = FigureCanvasTkAgg(
            fig,
            master=parent,
        )

        canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
        )

        _chart_cache[key] = {
            "fig": fig,
            "ax1": ax1,
            "ax2": ax2,
            "canvas": canvas,
            "parent": parent,
        }
    else:
        fig = _chart_cache[key]["fig"]
        ax1 = _chart_cache[key]["ax1"]
        ax2 = _chart_cache[key]["ax2"]
        canvas = _chart_cache[key]["canvas"]

    ax1.clear()
    ax2.clear()

    # 左軸：降水確率
    color_precip = "#4682b4"

    ax1.set_xlabel("時間")
    ax1.set_ylabel(
        "降水確率 (%)",
        color=color_precip,
    )

    ax1.bar(
        hours,
        precips,
        color=color_precip,
        alpha=0.6,
        width=0.6,
        label="降水確率",
    )

    ax1.tick_params(
        axis="y",
        labelcolor=color_precip,
    )

    ax1.set_ylim(0, 100)

    ax1.set_xlim(
        SafetyRule.ACTIVITY_START_HOUR - 0.5,
        SafetyRule.ACTIVITY_END_HOUR + 0.5,
    )

    ax1.set_xticks(
        range(
            SafetyRule.ACTIVITY_START_HOUR,
            SafetyRule.ACTIVITY_END_HOUR + 1,
        )
    )

    # 右軸：気温
    color_temp = "#ff4500"

    ax2.set_ylabel(
        "気温 (℃)",
        color=color_temp,
    )

    ax2.yaxis.set_label_position("right")
    ax2.yaxis.tick_right()

    ax2.plot(
        hours,
        temps,
        color=color_temp,
        marker="s",
        linewidth=2,
        label="気温",
    )

    ax2.tick_params(
        axis="y",
        labelcolor=color_temp,
    )

    if temps:
        t_min = min(temps)
        t_max = max(temps)

        ax2.set_ylim(
            max(0, t_min - 5),
            t_max + 5,
        )

    ax1.grid(
        True,
        linestyle="--",
        color="#DDDDDD",
        linewidth=0.5,
        axis="both",
    )

    ax1.set_axisbelow(True)

    fig.subplots_adjust(
        left=0.15,
        bottom=0.2,
        right=0.85,
        top=0.9,
    )

    canvas.draw()
