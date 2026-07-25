"""
desktop_charts.py

Tkinterアプリケーション（Matplotlib）で使用する海況グラフの描画ヘルパー。
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from engine import SafetyRule


def render_all_desktop_graphs(wind_tab, wave_tab, tide_tab, hour_data):
    """
    風速・波高・潮位のグラフを指定されたタブ内に一括描画する。

    Parameters:
        wind_tab (tk.Widget): 風速グラフを表示するタブ
        wave_tab (tk.Widget): 波高グラフを表示するタブ
        tide_tab (tk.Widget): 潮位グラフを表示するタブ
        hour_data (dict): 時間ごとの海況データ
    """
    plt.rcParams['font.family'] = 'Yu Gothic'
    
    for tab in [wind_tab, wave_tab, tide_tab]:
        for widget in tab.winfo_children():
            widget.destroy()

    # 活動時間外のデータを排除し、グラフの描画範囲を整えるためフィルタリングする
    filtered_items = {k: v for k, v in hour_data.items() if SafetyRule.ACTIVITY_START_HOUR <= int(k) <= SafetyRule.ACTIVITY_END_HOUR}
    
    hours = [int(k) for k in filtered_items.keys()]
    winds = [v.wind_speed for v in filtered_items.values()]
    waves = [v.wave_height for v in filtered_items.values()]
    tides = [float(v.tide) for v in filtered_items.values()]

    def draw(parent, data, ylabel, color, y_lim, threshold=None, threshold_label=None):
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        ax.plot(hours, data, color=color, marker="o")
        
        if threshold is not None:
            ax.axhline(
                y=threshold, 
                color="red", 
                linestyle="--", 
                linewidth=1.5, 
                label=threshold_label
            )
            if threshold_label:
                ax.legend(loc="upper right", fontsize=9)
        
        ax.set_xlabel("時刻")
        ax.set_ylabel(ylabel)
        
        ax.set_xlim(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR)
        ax.set_xticks(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
        ax.set_ylim(0, y_lim)
        
        ax.grid(True, linestyle='--', color='#DDDDDD', linewidth=0.5, axis='both')
        ax.set_axisbelow(True)
        
        plt.subplots_adjust(left=0.15, bottom=0.2, right=0.95, top=0.9)
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    draw(wind_tab, winds, "風速(m/s)", SafetyRule.WIND_COLOR, SafetyRule.WIND_Y_LIMIT, threshold=SafetyRule.WIND_LIMIT_NORMAL, threshold_label="制限風速")
    draw(wave_tab, waves, "波高(m)", SafetyRule.WAVE_COLOR, SafetyRule.WAVE_Y_LIMIT, threshold=SafetyRule.MAX_WAVE_HEIGHT_NORMAL, threshold_label="制限波高")
    draw(tide_tab, tides, "潮位(cm)", SafetyRule.TIDE_COLOR, SafetyRule.TIDE_Y_LIMIT, threshold=SafetyRule.MIN_TIDE_CM, threshold_label="最低潮位")
