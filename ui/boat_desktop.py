"""
boat_desktop.py

相模川河口のプレジャーボート出港判定アプリケーション。
Tkinterを用いたGUIの構築および、サービス層(BoatDataService)と連携した
海況判定の実行管理を担当します。
"""

import logging
import tkinter as tk
import datetime
import matplotlib.pyplot as plt
import os

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, ttk
from engine.loader import get_rule_content

from engine import (
    AnalysisResult, AnalysisSummary, SafetyRule, BoatSafetyEngine,
    SunCalculator, summarize_daytime_weather,
    TideFormatter, ReportFormatter, SafetyReportFormatter, StatusUIConfig
)
from services.analysis import BoatDataService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("BoatSafetyApp")

class BoatSafetyApp:
    """アプリケーションのメインクラス。"""
    
    def __init__(self, window_root: tk.Tk):
        self.root = window_root
        self.root.title("相模川河口 プレジャーボート海況安全判定アプリ")
        self.root.geometry("1000x720")
        self.root.configure(bg="#eef3f8")
        
        self._setup_styles()
        self._create_layout()
        self.menu_win = None

    def _setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=30, font=("Yu Gothic UI", 10))
        self.style.configure("Treeview.Heading", font=("Yu Gothic UI", 10, "bold"))

    def _create_layout(self):
        header = tk.Frame(self.root, bg="#0b4f6c", height=65)
        header.pack(fill="x")
        
        # タイトル調整用の空ラベル
        tk.Label(header, width=5, bg="#0b4f6c").pack(side="left") 
        
        # タイトル
        tk.Label(header, text="🚤 ボート出港判定", bg="#0b4f6c", fg="white", font=("Yu Gothic UI", 18, "bold")).pack(side="left", expand=True, pady=15)
        
        # メニューボタン追加
        self.menu_btn = tk.Button(
            header, text="≡", bg="#0b4f6c", fg="white", font=("Yu Gothic UI", 20), 
            relief="flat", cursor="hand2", command=self.show_menu_popup
        )
        self.menu_btn.pack(side="right", padx=15)
        
        tk.Label(self.root, text="※相模川河口の潮位・潮汐・風速・風向・波高・うねりを総合評価", bg="#eef3f8", fg="#555555", font=("Yu Gothic UI", 9, "italic")).pack(pady=(5, 5))

        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        date_frame = tk.LabelFrame(self.root, text=" 判定日 ", bg="white", padx=10, pady=5)
        date_frame.pack(fill="x", padx=20, pady=5)
        
        date_options = []
        JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
        today_jst = datetime.datetime.now(JST).date()

        for i in range(8):
            d = today_jst + datetime.timedelta(days=i)
            date_str = f"{d.strftime('%Y-%m-%d')}({weekdays[d.weekday()]})"
            date_options.append(date_str)
            
        self.date_combobox = ttk.Combobox(date_frame, values=date_options, state="readonly", width=20)
        self.date_combobox.set(date_options[0])
        self.date_combobox.pack(side=tk.LEFT, padx=5)

        self.submit_btn = tk.Button(
            self.root, text="🔍 海況判定を実行する", command=self.on_click_check,
            bg="#0078D7", fg="white", font=("Yu Gothic UI", 12, "bold"), relief="flat", padx=25, pady=8, cursor="hand2"
        )
        self.submit_btn.pack(pady=12)

        status_panel = tk.Frame(self.root, bg="white", bd=1, relief="solid")
        status_panel.pack(fill="x", padx=20, pady=5)

        self.result_label = tk.Label(status_panel, text="未判定", bg="white", fg="gray", font=("Yu Gothic UI", 26, "bold"))
        self.result_label.pack()
        self.weather_label = tk.Label(status_panel, text="", bg="white", fg="#0b4f6c", font=("Yu Gothic UI", 11, "bold"))
        self.weather_label.pack(pady=2)
        self.summary_label = tk.Label(status_panel, text="", bg="white", font=("Yu Gothic UI", 10), justify="center")
        self.summary_label.pack(pady=(2, 8))

        self.tide_info_label = tk.Label(self.root, text="", bg="#eef3f8", fg="#444444", font=("Yu Gothic UI", 9, "bold"))
        self.tide_info_label.pack(pady=2)

        # 1. 既存の notebook 作成部分はそのまま
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        # 2. タブを3つ定義する
        self.table_tab = tk.Frame(self.notebook)
        self.notebook.add(self.table_tab, text="📊 判定結果")
        
        self.wind_tab = tk.Frame(self.notebook)
        self.notebook.add(self.wind_tab, text="💨 風速グラフ")
        
        self.wave_tab = tk.Frame(self.notebook)
        self.notebook.add(self.wave_tab, text="🌊 波高グラフ")
        
        self.tide_tab = tk.Frame(self.notebook)
        self.notebook.add(self.tide_tab, text="🌊 潮位グラフ")

        # 3. Treeview の親を self.table_tab に設定
        COLUMNS = ("time", "status", "direction", "wind", "wave", "tide")
        TABLE_HEADERS = {"time": "時間", "status": "判定", "direction": "風向", "wind": "風速", "wave": "波浪", "tide": "潮位"}
       
        # 親を self.table_tab に指定
        self.result_tree = ttk.Treeview(self.table_tab, columns=COLUMNS, show="headings", height=12)
        for col_key, header_title in TABLE_HEADERS.items():
            self.result_tree.heading(col_key, text=header_title)
            self.result_tree.column(col_key, width=135, anchor="center", stretch=True)

        tree_scroll = ttk.Scrollbar(self.table_tab, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=tree_scroll.set)

        self.result_tree.tag_configure("safe", background="#e8f5e9")
        self.result_tree.tag_configure("danger", background="#ffebee")
        self.result_tree.tag_configure("tide_low", background="#fff8e1")

        self.result_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")


    def on_click_check(self) -> None:
        raw_date_str = self.date_combobox.get()
        if not raw_date_str:
            messagebox.showwarning("警告", "日付を選択してください。")
            return

        target_date_str = raw_date_str[:10]
        self.submit_btn.config(state=tk.DISABLED, text="⏳ 解析処理中...")
        self.result_label.config(text="データオンライン取得中...", fg="orange")
        for item in self.result_tree.get_children(): self.result_tree.delete(item)
        
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self._async_fetch_and_judge, target_date_str, target_date)

    def _async_fetch_and_judge(self, target_date_str: str, target_date: datetime.date) -> None:
        try:
            result = BoatDataService.get_full_analysis(target_date)
            self.root.after(0, self._sync_render_ui, result)
        except Exception as e:
            logger.error(f"非同期データ処理タスクに異常障害を検知: {e}")
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self._handle_async_error(msg))

    def _sync_render_ui(self, result: AnalysisResult) -> None:
        self.submit_btn.config(state=tk.DISABLED, text="取得・解析中...")
        try:
            if not result or not result.weather_info:
                messagebox.showerror("エラー", "気象データの取得または解析に失敗しました。")
                self.result_label.config(text="未判定(通信エラー)", fg="gray")
                return

            weather_info, umi_info, hour_data, summary = result.weather_info, result.umi_info, result.hour_data, result.summary

            daytime_summary = summarize_daytime_weather(weather_info.weather_code, weather_info.precipitation_probability)
            self.weather_label.config(text=f"{daytime_summary} | 【{weather_info.temp_max:.0f}℃ / {weather_info.temp_min:.0f}℃】")

            self.result_tree.delete(*self.result_tree.get_children())
            sunrise_hour, sunset_hour = SunCalculator.get_sun_times(umi_info)
            table_rows = SafetyReportFormatter.build_table_rows(hour_data, sunrise_hour, sunset_hour)

            # 1. 全データを生成
            all_rows = ReportFormatter.build_display_rows(table_rows)

            # 2. テーブル用: フィルタリング適用後のものだけを表示
            display_rows_filtered = ReportFormatter.filter_display_rows(all_rows)
            for row in display_rows_filtered:
                self.result_tree.insert("", "end", values=(row.time_range, row.status, row.direction, row.wind, row.wave, row.tide), tags=(row.tag,))

            # 3. グラフ用: hour_data をそのまま渡す（_render_all_graphs内で制御）
            self._render_all_graphs(hour_data)

            ui_data = SafetyReportFormatter.get_ui_summary_data(summary)
            self.result_label.config(text=f" {ui_data['label']}", fg=ui_data['color'])
            self.summary_label.config(text=ui_data['text'], fg=ui_data['color'])
            self.tide_info_label.config(text=TideFormatter.get_ui_tide_text(umi_info))
        finally:
            self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")

    def _render_all_graphs(self, hour_data):
        plt.rcParams['font.family'] = 'Yu Gothic'
        
        # 各タブをクリア
        for tab in [self.wind_tab, self.wave_tab, self.tide_tab]:
            for widget in tab.winfo_children():
                widget.destroy()

        # 18時までのデータのみにフィルタリングしてリスト化
        filtered_items = {k: v for k, v in hour_data.items() if SafetyRule.ACTIVITY_START_HOUR <= int(k) <= SafetyRule.ACTIVITY_END_HOUR}
        
        hours = [int(k) for k in filtered_items.keys()]
        winds = [v.wind_speed for v in filtered_items.values()]
        waves = [v.wave_height for v in filtered_items.values()]
        tides = [float(v.tide) for v in filtered_items.values()]

        # 描画用内部関数
        def draw(parent, data, ylabel, color, y_lim):
            fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
            ax.plot(hours, data, color=color, marker="o")
            
            ax.set_xlabel("時刻")
            ax.set_ylabel(ylabel)
            
            # 定数を使用して表示範囲を制御
            ax.set_xlim(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR)
            ax.set_xticks(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
            ax.set_ylim(0, y_lim)
            
            # グリッド設定
            ax.grid(True, linestyle='--', color='#DDDDDD', linewidth=0.5, axis='both')
            ax.set_axisbelow(True)
            
            plt.subplots_adjust(left=0.15, bottom=0.2, right=0.95, top=0.9)
            
            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

        draw(self.wind_tab, winds, "風速(m/s)", "blue", 15)
        draw(self.wave_tab, waves, "波高(m)", "red", 3)
        draw(self.tide_tab, tides, "潮位(cm)", "green", 300)

    def _handle_async_error(self, err_msg: str) -> None:
        self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")
        self.result_label.config(text="未判定(通信・内部エラー)", fg="gray")
        messagebox.showerror("致命的エラー", f"非同期判定タスクの駆動中にエラーが検出されました:\n{err_msg}")

    def show_menu_popup(self):
        menu = tk.Menu(self.root, tearoff=0, font=("Yu Gothic UI", 10))
        
        # 1. 判定基準の確認
        menu.add_command(label="判定基準を確認", command=self._show_safety_criteria)
        menu.add_separator()
        
        # 2. 4分割したチェックリストメニュー
        checklist_map = [
            ("PRE_LOWER", "下架前チェック", "下架前チェックリスト"),
            ("POST_LOWER", "下架後チェック", "下架後チェックリスト"),
            ("PRE_LIFT", "上架前チェック", "上架前チェックリスト"),
            ("POST_LIFT", "上架後チェック", "上架後チェックリスト")
        ]
        for key, label, title in checklist_map:
            menu.add_command(label=label, command=lambda k=key, t=title: self._open_checklist(k, t))
        
        menu.add_separator()
        menu.add_command(label="⚙ 設定", command=self._on_settings_select)
        
        x = self.root.winfo_rootx() + self.root.winfo_width() - 200
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height()
        menu.post(x, y)

    def _open_checklist(self, section_key, title):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("350x600")

        # 1. 閉じるボタン
        tk.Button(top, text="閉じる", command=top.destroy, bg="#eeeeee").pack(fill="x", pady=5)

        # 2. スクロールバーとリストボックスを配置
        frame = tk.Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame, orient="vertical")
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, selectmode="extended", font=("Yu Gothic UI", 12))
        
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.pack(side="left", fill="both", expand=True)


        items = get_rule_content(section_key)
        for item in items:
            listbox.insert("end", "☐ " + item)

        # 4. クリックでチェック切り替え
        def on_select(event):
            index = listbox.curselection()
            if index:
                item = listbox.get(index[0])
                if item.startswith("☐"):
                    listbox.delete(index[0])
                    listbox.insert(index[0], "☑ " + item[2:])
                else:
                    listbox.delete(index[0])
                    listbox.insert(index[0], "☐ " + item[2:])
                listbox.selection_clear(0, "end")
        
        listbox.bind("<<ListboxSelect>>", on_select)

    def _show_safety_criteria(self):
        file_path = os.path.join(os.path.dirname(__file__), "safety_criteria.txt")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            messagebox.showinfo("判定基準", content)
        except Exception as e:
            messagebox.showerror("エラー", f"基準ファイルの読み込みに失敗しました: {e}")

    def _on_settings_select(self):
        messagebox.showinfo("設定", "設定画面は現在準備中です。")


def run_boat_desktop():
    main_window = tk.Tk()
    app = BoatSafetyApp(main_window)
    main_window.mainloop()

if __name__ == "__main__":
    run_boat_desktop()
