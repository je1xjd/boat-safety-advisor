"""
boat_desktop.py

相模川河口のプレジャーボート出港判定アプリケーション。
Tkinterを用いたGUIの構築および、サービス層(BoatDataService)と連携した
海況判定の実行管理を担当します。
"""

import datetime
import logging
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, ttk

from engine import (
    AnalysisResult,
    BoatSafetyEngine,
    ReportFormatter,
    SafetyReportFormatter,
    SunCalculator,
    TideFormatter,
    summarize_daytime_weather,
)
from engine.loader import get_rule_content
from services.analysis import BoatDataService
from ui.desktop_charts import render_all_desktop_graphs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("BoatSafetyApp")


class BoatSafetyApp:
    """
    アプリケーションのメインクラス。
    UI全体の初期化、イベントハンドリング、非同期データ処理の連携を管理する。
    """

    def __init__(self, window_root: tk.Tk):
        self.root = window_root
        self.root.title("相模川河口 プレジャーボート海況安全判定アプリ")
        self.root.geometry("1000x720")
        self.root.configure(bg="#eef3f8")

        self._setup_styles()
        self._create_layout()
        self.menu_win = None

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """アプリ終了時にスレッドプールとグラフリソースを安全にシャットダウンして破棄する"""
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

        try:
            from ui.desktop_charts import dispose_desktop_graphs
            dispose_desktop_graphs()
        except Exception:
            pass

        self.root.destroy()

    def _setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=30, font=("Yu Gothic UI", 10))
        self.style.configure("Treeview.Heading", font=("Yu Gothic UI", 10, "bold"))

    def _create_layout(self):
        self._create_header_area()
        self._create_date_area()
        self._create_result_area()
        self._create_graph_area()

    def _create_header_area(self):
        """
        ヘッダー部分のUI部品を作成する。
        """
        header = tk.Frame(self.root, bg="#0b4f6c", height=65)
        header.pack(fill="x")

        tk.Label(header, width=5, bg="#0b4f6c").pack(side="left")

        tk.Label(
            header,
            text="🚤 ボート出港判定",
            bg="#0b4f6c",
            fg="white",
            font=("Yu Gothic UI", 18, "bold"),
        ).pack(side="left", expand=True, pady=15)

        self.menu_btn = tk.Button(
            header,
            text="≡",
            bg="#0b4f6c",
            fg="white",
            font=("Yu Gothic UI", 20),
            relief="flat",
            cursor="hand2",
            command=self.show_menu_popup,
        )
        self.menu_btn.pack(side="right", padx=15)

        tk.Label(
            self.root,
            text="※相模川河口の潮位・潮汐・風速・風向・波高・うねりを総合評価",
            bg="#eef3f8",
            fg="#555555",
            font=("Yu Gothic UI", 9, "italic"),
        ).pack(pady=(5, 5))

    def _create_date_area(self):
        """
        判定日の選択および実行ボタン部分のUIを作成する。
        """
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        date_frame = tk.LabelFrame(
            self.root, text=" 判定日 ", bg="white", padx=10, pady=5
        )
        date_frame.pack(fill="x", padx=20, pady=5)

        date_options = []
        JST = datetime.timezone(datetime.timedelta(hours=9), "JST")
        today_jst = datetime.datetime.now(JST).date()

        for i in range(8):
            d = today_jst + datetime.timedelta(days=i)
            date_options.append(f"{d.strftime('%Y-%m-%d')}({weekdays[d.weekday()]})")

        self.date_combobox = ttk.Combobox(
            date_frame, values=date_options, state="readonly", width=20
        )
        self.date_combobox.set(date_options[0])
        self.date_combobox.pack(side=tk.LEFT, padx=5)

        self.submit_btn = tk.Button(
            self.root,
            text="🔍 海況判定を実行する",
            command=self.on_click_check,
            bg="#0078D7",
            fg="white",
            font=("Yu Gothic UI", 12, "bold"),
            relief="flat",
            padx=25,
            pady=8,
            cursor="hand2",
        )
        self.submit_btn.pack(pady=12)

    def _create_result_area(self):
        """
        判定結果のサマリーパネルおよび潮位情報部分を作成する。
        """
        status_panel = tk.Frame(self.root, bg="white", bd=1, relief="solid")
        status_panel.pack(fill="x", padx=20, pady=5)

        self.result_label = tk.Label(
            status_panel,
            text="未判定",
            bg="white",
            fg="gray",
            font=("Yu Gothic UI", 26, "bold"),
        )
        self.result_label.pack()
        self.weather_label = tk.Label(
            status_panel,
            text="",
            bg="white",
            fg="#0b4f6c",
            font=("Yu Gothic UI", 11, "bold"),
        )
        self.weather_label.pack(pady=2)
        self.summary_label = tk.Label(
            status_panel,
            text="",
            bg="white",
            font=("Yu Gothic UI", 10),
            justify="center",
        )
        self.summary_label.pack(pady=(2, 8))

        self.tide_info_label = tk.Label(
            self.root,
            text="",
            bg="#eef3f8",
            fg="#444444",
            font=("Yu Gothic UI", 9, "bold"),
        )
        self.tide_info_label.pack(pady=2)

    def _create_graph_area(self):
        """
        詳細データおよび各種グラフを表示するタブ・ツリービュー領域を作成する。
        """
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        self.table_tab = tk.Frame(self.notebook)
        self.notebook.add(self.table_tab, text="📊 判定結果")

        self.wind_tab = tk.Frame(self.notebook)
        self.notebook.add(self.wind_tab, text="🍃 風速グラフ")

        self.wave_tab = tk.Frame(self.notebook)
        self.notebook.add(self.wave_tab, text="🌊 波高グラフ")

        self.tide_tab = tk.Frame(self.notebook)
        self.notebook.add(self.tide_tab, text="🚢 潮位グラフ")

        self.precip_tab = tk.Frame(self.notebook)
        self.notebook.add(self.precip_tab, text="🌧 降水・気温")

        COLUMNS = (
            "time",
            "status",
            "direction",
            "wind",
            "wave",
            "tide",
            "precip",
            "temp",
        )
        TABLE_HEADERS = {
            "time": "時間",
            "status": "判定",
            "direction": "風向",
            "wind": "風速",
            "wave": "波高",
            "tide": "潮位",
            "precip": "降水",
            "temp": "気温",
        }

        self.result_tree = ttk.Treeview(
            self.table_tab, columns=COLUMNS, show="headings", height=12
        )
        for col_key, header_title in TABLE_HEADERS.items():
            self.result_tree.heading(col_key, text=header_title)
            width = 85 if col_key in ("precip", "temp") else 110
            self.result_tree.column(col_key, width=width, anchor="center", stretch=True)

        tree_scroll = ttk.Scrollbar(
            self.table_tab, orient="vertical", command=self.result_tree.yview
        )
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
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        
        self.executor.submit(self._async_fetch_and_judge, target_date)

    def _async_fetch_and_judge(
        self, target_date: datetime.date
    ) -> None:
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
                messagebox.showerror(
                    "エラー", "気象データの取得または解析に失敗しました。"
                )
                self.result_label.config(text="未判定(通信エラー)", fg="gray")
                return

            weather_info, umi_info, hour_data, summary = (
                result.weather_info,
                result.umi_info,
                result.hour_data,
                result.summary,
            )

            daytime_summary = summarize_daytime_weather(
                weather_info.weather_code, weather_info.precipitation_probability
            )
            self.weather_label.config(
                text=f"{daytime_summary} | 【{weather_info.temp_max:.0f}℃ / {weather_info.temp_min:.0f}℃】"
            )

            self.result_tree.delete(*self.result_tree.get_children())
            sunrise_time, sunset_time = SunCalculator.get_sun_times(umi_info)

            # 💡 ルール適用処理
            high_tides = getattr(umi_info, "high_tides", getattr(umi_info, "high_tide_list", []))
            low_tides = getattr(umi_info, "low_tides", getattr(umi_info, "low_tide_list", []))

            BoatSafetyEngine.apply_sequence_rules(
                hour_data, 
                sunrise_time, 
                sunset_time, 
                high_tides, 
                low_tides
            )

            table_rows = SafetyReportFormatter.build_table_rows(
                hour_data, sunrise_time, sunset_time
            )

            all_rows = ReportFormatter.build_display_rows(table_rows)
            display_rows_filtered = ReportFormatter.filter_display_rows(all_rows)
            for row in display_rows_filtered:
                self.result_tree.insert(
                    "",
                    "end",
                    values=(
                        row.time_range,
                        row.status,
                        row.direction,
                        row.wind,
                        row.wave,
                        row.tide,
                        row.precip,
                        row.temp,
                    ),
                    tags=(row.tag,),
                )

            render_all_desktop_graphs(
                self.wind_tab, self.wave_tab, self.tide_tab, self.precip_tab, hour_data
            )

            ui_data = SafetyReportFormatter.get_ui_summary_data(summary)
            self.result_label.config(text=f" {ui_data['label']}", fg=ui_data["color"])
            self.summary_label.config(text=ui_data["text"], fg=ui_data["color"])
            self.tide_info_label.config(text=TideFormatter.get_ui_tide_text(umi_info))
        finally:
            self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")

    def _handle_async_error(self, err_msg: str) -> None:
        self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")
        self.result_label.config(text="未判定(通信・内部エラー)", fg="gray")
        messagebox.showerror(
            "致命的エラー",
            f"非同期判定タスクの駆動中にエラーが検出されました:\n{err_msg}",
        )

    def show_menu_popup(self):
        """
        メイン画面右上のハンバーガーメニューからポップアップメニューを表示する。
        """
        menu = tk.Menu(self.root, tearoff=0, font=("Yu Gothic UI", 10))

        menu.add_command(label="⚖ 判定基準", command=self._show_safety_criteria)
        menu.add_separator()

        menu.add_command(label="🚀 【出港前】", state="disabled")
        menu.add_command(
            label=" 下架前チェック",
            command=lambda: self._open_checklist("PRE_LOWER", "下架前チェックリスト"),
        )
        menu.add_command(
            label=" 下架後チェック",
            command=lambda: self._open_checklist("POST_LOWER", "下架後チェックリスト"),
        )
        menu.add_separator()

        menu.add_command(label="⚓ 【帰港後】", state="disabled")
        menu.add_command(
            label=" 上架前チェック",
            command=lambda: self._open_checklist("PRE_LIFT", "上架前チェックリスト"),
        )
        menu.add_command(
            label=" 上架後チェック",
            command=lambda: self._open_checklist("POST_LIFT", "上架後チェックリスト"),
        )

        menu.add_separator()
        menu.add_command(label="⚙ 設定", command=self._on_settings_select)

        x = self.root.winfo_rootx() + self.root.winfo_width() - 200
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height()
        menu.post(x, y)

    def _create_checklist_widgets(
        self, top, listbox, scrollbar, items, is_criteria=False
    ):
        """
        チェックリストおよび判定基準画面のUI部品を配置・構築するために処理をまとめる。
        """
        tk.Button(
            top,
            text="閉じる",
            command=top.destroy,
            bg="#eeeeee",
            font=("Yu Gothic UI", 10 if is_criteria else 12),
        ).pack(fill="x", pady=5)

        frame = tk.Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.pack(side="left", fill="both", expand=True)

        for item in items:
            listbox.insert("end", item if is_criteria else "☐ " + item)

    def _open_checklist(self, section_key, title):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("350x600")

        frame = tk.Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame, orient="vertical")
        listbox = tk.Listbox(
            frame,
            yscrollcommand=scrollbar.set,
            selectmode="extended",
            font=("Yu Gothic UI", 12),
        )

        items = get_rule_content(section_key)
        self._create_checklist_widgets(
            top, listbox, scrollbar, items, is_criteria=False
        )

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
        top = tk.Toplevel(self.root)
        top.title("ボート出港安全基準")
        top.geometry("450x600")

        frame = tk.Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame, orient="vertical")
        listbox = tk.Listbox(
            frame, yscrollcommand=scrollbar.set, font=("Yu Gothic UI", 11)
        )

        items = get_rule_content("SAFETY_CRITERIA")
        self._create_checklist_widgets(top, listbox, scrollbar, items, is_criteria=True)

    def _on_settings_select(self):
        messagebox.showinfo("設定", "設定画面は現在準備中です。")


def run_boat_desktop():
    """
    デスクトップアプリケーションを起動するエントリポイント。
    """
    main_window = tk.Tk()
    app = BoatSafetyApp(main_window)
    main_window.mainloop()


if __name__ == "__main__":
    run_boat_desktop()
