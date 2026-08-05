"""
desktop_charts.py

Tkinterアプリケーション（Matplotlib）で使用する海況グラフの描画ヘルパー。
初回起動時にFigureとCanvasを初期化し、更新時は再利用（ax.clear）する設計。
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from engine import SafetyRule
from engine import WindJudge


# モジュールロード時に1回だけフォントを設定
plt.rcParams["font.family"] = "Yu Gothic"

# モジュールレベルのキャッシュ
_chart_cache = {}


def dispose_desktop_graphs():
    """アプリケーション終了時にFigure・Canvasを明示的に安全破棄する"""
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


def render_all_desktop_graphs(wind_tab, wave_tab, tide_tab, precip_tab, hour_data):
    """
    風速・波高・潮位・降水気温のグラフを指定されたタブ内に一括描画する（キャッシュ再利用方式）。
    """
    filtered_items = {
        k: v
        for k, v in hour_data.items()
        if SafetyRule.ACTIVITY_START_HOUR <= int(k) <= SafetyRule.ACTIVITY_END_HOUR
    }

    hours = [int(k) for k in filtered_items]
    winds = [v.wind_speed for v in filtered_items.values()]
    waves = [v.wave_height for v in filtered_items.values()]
    tides = [float(v.tide) for v in filtered_items.values()]

    precips = [
        getattr(v, "precipitation_probability", 0) for v in filtered_items.values()
    ]
    temps = [getattr(v, "temperature", 0) for v in filtered_items.values()]

    # --- 1. 風速グラフ（時間ごとの動的風速制限値の算出） ---
    wind_limits = []
    for h, v in filtered_items.items():
        is_south = WindJudge.is_south_wind(getattr(v, "wind_dir", 0))
        is_ebb = getattr(v, "is_ebb", False) # オブジェクトが保持する下げ潮フラグ（または潮位データから算出）
        wave_h = getattr(v, "wave_height", 0)

        # 時間ごとの制限風速を算出 (南風&下げ潮:5.5m/s, 下げ潮のみ:7.0m/s, 南風のみ:7.5m/s, その他:9.0m/s)
        limit = WindJudge.get_limit(is_ebb, is_south, wave_h <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL)
        wind_limits.append(limit)

    _update_or_create_single_chart(
        wind_tab, "wind", hours, winds,
        ylabel="風速(m/s)", color=SafetyRule.WIND_COLOR, y_lim=SafetyRule.WIND_Y_LIMIT,
        threshold=wind_limits, threshold_label="制限風速"
    )

    # --- 2. 波高グラフ（時間ごとの動的波高制限値の算出） ---
    wave_limits = []
    for h, v in filtered_items.items():
        is_south = WindJudge.is_south_wind(getattr(v, "wind_dir", 0))
        is_ebb = getattr(v, "is_ebb", False)

        # 南風または下げ潮時は制限が厳しくなり 0.8m、通常時は 1.0m
        if is_south or is_ebb:
            wave_limits.append(SafetyRule.MAX_WAVE_HEIGHT_STRICT)
        else:
            wave_limits.append(SafetyRule.MAX_WAVE_HEIGHT_NORMAL)

    _update_or_create_single_chart(
        wave_tab, "wave", hours, waves,
        ylabel="波高(m)", color=SafetyRule.WAVE_COLOR, y_lim=SafetyRule.WAVE_Y_LIMIT,
        threshold=wave_limits, threshold_label="制限波高"
    )

    # --- 3. 潮位グラフ ---
    _update_or_create_single_chart(
        tide_tab, "tide", hours, tides,
        ylabel="潮位(cm)", color=SafetyRule.TIDE_COLOR, y_lim=SafetyRule.TIDE_Y_LIMIT,
        threshold=SafetyRule.MIN_TIDE_CM, threshold_label="最低潮位"
    )

    # --- 4. 降水・気温グラフ（2軸） ---
    _update_or_create_dual_chart(
        precip_tab, "precip_temp", hours, precips, temps
    )


def _update_or_create_single_chart(parent, key, hours, data, ylabel, color, y_lim, threshold=None, threshold_label=None):
    """単一軸グラフの初回作成または既存キャッシュのクリア＆再描画を行う"""
    if key not in _chart_cache or _chart_cache[key]["parent"] != parent:
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        _chart_cache[key] = {"fig": fig, "ax": ax, "canvas": canvas, "parent": parent}
    else:
        fig = _chart_cache[key]["fig"]
        ax = _chart_cache[key]["ax"]
        canvas = _chart_cache[key]["canvas"]

    ax.clear()
    ax.plot(hours, data, color=color, marker="o")

    if threshold is not None:
        if isinstance(threshold, (list, tuple)):
            # 💡 各時間の閾値を折れ線としてプロット
            ax.plot(
                hours,
                threshold,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=threshold_label,
            )
        else:
            # 単一の固定閾値（従来の水平線）
            ax.axhline(
                y=threshold,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=threshold_label,
            )
        if threshold_label:
            ax.legend(loc="upper right", fontsize=9)

    ax.set_xlabel("時間")
    ax.set_ylabel(ylabel)

    ax.set_xlim(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR)
    ax.set_xticks(
        range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1)
    )
    ax.set_ylim(0, y_lim)

    ax.grid(True, linestyle="--", color="#DDDDDD", linewidth=0.5, axis="both")
    ax.set_axisbelow(True)

    fig.subplots_adjust(left=0.15, bottom=0.2, right=0.95, top=0.9)
    canvas.draw()


def _update_or_create_dual_chart(parent, key, hours, precips, temps):
    """降水・気温の2軸グラフの初回作成または既存キャッシュのクリア＆再描画を行う"""
    if key not in _chart_cache or _chart_cache[key]["parent"] != parent:
        fig, ax1 = plt.subplots(figsize=(6, 4), dpi=100)
        ax2 = ax1.twinx()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        _chart_cache[key] = {"fig": fig, "ax1": ax1, "ax2": ax2, "canvas": canvas, "parent": parent}
    else:
        fig = _chart_cache[key]["fig"]
        ax1 = _chart_cache[key]["ax1"]
        ax2 = _chart_cache[key]["ax2"]
        canvas = _chart_cache[key]["canvas"]

    ax1.clear()
    ax2.clear()  # 💡既存のax2をクリアして再利用する（毎回twinxを作らない）

    # 左軸：降水確率（棒グラフ）
    color_precip = "#4682b4"
    ax1.set_xlabel("時間")
    ax1.set_ylabel("降水確率 (%)", color=color_precip)
    ax1.bar(
        hours, precips, color=color_precip, alpha=0.6, width=0.6, label="降水確率"
    )
    ax1.tick_params(axis="y", labelcolor=color_precip)
    ax1.set_ylim(0, 100)
    ax1.set_xlim(
        SafetyRule.ACTIVITY_START_HOUR - 0.5, SafetyRule.ACTIVITY_END_HOUR + 0.5
    )
    ax1.set_xticks(
        range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1)
    )

    # 右軸：気温（折れ線グラフ）
    color_temp = "#ff4500"  # オレンジレッド
    ax2.set_ylabel("気温 (℃)", color=color_temp)
    
    ax2.yaxis.set_label_position("right")
    ax2.yaxis.tick_right()

    line = ax2.plot(
        hours, temps, color=color_temp, marker="s", linewidth=2, label="気温"
    )
    ax2.tick_params(axis="y", labelcolor=color_temp)

    if temps:
        t_min = min(temps)
        t_max = max(temps)
        ax2.set_ylim(max(0, t_min - 5), t_max + 5)

    ax1.grid(True, linestyle="--", color="#DDDDDD", linewidth=0.5, axis="both")
    ax1.set_axisbelow(True)

    fig.subplots_adjust(left=0.15, bottom=0.2, right=0.85, top=0.9)
    canvas.draw()
