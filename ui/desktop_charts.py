"""
desktop_charts.py

Tkinterアプリケーション（Matplotlib）で使用する海況グラフの描画ヘルパー。
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from engine import SafetyRule


def render_all_desktop_graphs(wind_tab, wave_tab, tide_tab, precip_tab, hour_data):
    """
    風速・波高・潮位・降水気温のグラフを指定されたタブ内に一括描画する。

    Parameters:
        wind_tab (tk.Widget): 風速グラフを表示するタブ
        wave_tab (tk.Widget): 波高グラフを表示するタブ
        tide_tab (tk.Widget): 潮位グラフを表示するタブ
        precip_tab (tk.Widget): 降水・気温グラフを表示するタブ
        hour_data (dict): 時間ごとの海況データ
    """
    plt.rcParams["font.family"] = "Yu Gothic"

    for tab in [wind_tab, wave_tab, tide_tab, precip_tab]:
        for widget in tab.winfo_children():
            widget.destroy()

    # 活動時間外のデータを排除し、グラフの描画範囲を整えるためフィルタリングする
    filtered_items = {
        k: v
        for k, v in hour_data.items()
        if SafetyRule.ACTIVITY_START_HOUR <= int(k) <= SafetyRule.ACTIVITY_END_HOUR
    }

    hours = [int(k) for k in filtered_items]
    winds = [v.wind_speed for v in filtered_items.values()]
    waves = [v.wave_height for v in filtered_items.values()]
    tides = [float(v.tide) for v in filtered_items.values()]

    # 降水確率と気温のデータを抽出（HourForecastに precip_prob や temp があると仮定、属性名に合わせて調整してください）
    # ※もし属性名が異なる場合は合わせます
    precips = [
        getattr(v, "precipitation_probability", 0) for v in filtered_items.values()
    ]
    temps = [getattr(v, "temperature", 0) for v in filtered_items.values()]

    def draw(parent, data, ylabel, color, y_lim, threshold=None, threshold_label=None):
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        ax.plot(hours, data, color=color, marker="o")

        if threshold is not None:
            ax.axhline(
                y=threshold,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=threshold_label,
            )
            if threshold_label:
                ax.legend(loc="upper right", fontsize=9)

        ax.set_xlabel("時刻")
        ax.set_ylabel(ylabel)

        ax.set_xlim(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR)
        ax.set_xticks(
            range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1)
        )
        ax.set_ylim(0, y_lim)

        ax.grid(True, linestyle="--", color="#DDDDDD", linewidth=0.5, axis="both")
        ax.set_axisbelow(True)

        plt.subplots_adjust(left=0.15, bottom=0.2, right=0.95, top=0.9)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        plt.close(fig)

    def draw_precip_temp(parent, hours, precips, temps):
        """降水確率（棒グラフ）と気温（折れ線グラフ）の2軸複合グラフを描画する"""
        fig, ax1 = plt.subplots(figsize=(6, 4), dpi=100)

        # 左軸：降水確率（棒グラフ）
        color_precip = "#4682b4"  # スレートブルー
        ax1.set_xlabel("時刻")
        ax1.set_ylabel("降水確率 (%)", color=color_precip)
        bars = ax1.bar(
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
        ax2 = ax1.twinx()
        color_temp = "#ff4500"  # オレンジレッド
        ax2.set_ylabel("気温 (℃)", color=color_temp)
        line = ax2.plot(
            hours, temps, color=color_temp, marker="s", linewidth=2, label="気温"
        )
        ax2.tick_params(axis="y", labelcolor=color_temp)

        # 気温のY軸レンジをデータのmin/maxに合わせて余裕を持たせる
        if temps:
            t_min = min(temps)
            t_max = max(temps)
            ax2.set_ylim(max(0, t_min - 5), t_max + 5)

        ax1.grid(True, linestyle="--", color="#DDDDDD", linewidth=0.5, axis="both")
        ax1.set_axisbelow(True)

        plt.subplots_adjust(left=0.15, bottom=0.2, right=0.85, top=0.9)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        plt.close(fig)

    draw(
        wind_tab,
        winds,
        "風速(m/s)",
        SafetyRule.WIND_COLOR,
        SafetyRule.WIND_Y_LIMIT,
        threshold=SafetyRule.WIND_LIMIT_NORMAL,
        threshold_label="制限風速",
    )
    draw(
        wave_tab,
        waves,
        "波高(m)",
        SafetyRule.WAVE_COLOR,
        SafetyRule.WAVE_Y_LIMIT,
        threshold=SafetyRule.MAX_WAVE_HEIGHT_NORMAL,
        threshold_label="制限波高",
    )
    draw(
        tide_tab,
        tides,
        "潮位(cm)",
        SafetyRule.TIDE_COLOR,
        SafetyRule.TIDE_Y_LIMIT,
        threshold=SafetyRule.MIN_TIDE_CM,
        threshold_label="最低潮位",
    )
    draw_precip_temp(precip_tab, hours, precips, temps)
