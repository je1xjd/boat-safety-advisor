import logging
import tkinter as tk
import datetime

from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, ttk

from engine import AnalysisResult, AnalysisSummary
from engine import SafetyRule
from engine import BoatSafetyEngine
from engine import (
    SunCalculator, 
    summarize_daytime_weather, 
)

from engine import (
    TideFormatter, 
    ReportFormatter, 
    SafetyReportFormatter, 
    StatusUIConfig
)
from services.analysis import BoatDataService

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("BoatSafetyApp")



# ==============================================================================
# UI表示レイヤー
# ==============================================================================
class BoatSafetyApp:
    """
    アプリケーションのグラフィカルインターフェースを管理するメインクラス。
    Tkinterを用いて海況安全情報を表示し、ユーザー操作を受け付けます。
    """
    
    def __init__(self, window_root: tk.Tk):
        """UIの初期化およびレイアウト構築の実行"""
        self.root = window_root
        self.root.title("相模川河口 プレジャーボート海況安全判定アプリ")
        self.root.geometry("1000x720")
        self.root.configure(bg="#eef3f8")
        
        self._setup_styles()
        self._create_layout()

    def _setup_styles(self):
        """Treeview等のウィジェットに対する視覚的なスタイル設定"""
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=30, font=("Yu Gothic UI", 10))
        self.style.configure("Treeview.Heading", font=("Yu Gothic UI", 10, "bold"))

    def _create_layout(self):
        """アプリケーションのGUIレイアウトを生成する"""
        # ヘッダー
        header = tk.Frame(self.root, bg="#0b4f6c", height=65)
        header.pack(fill="x")
        tk.Label(header, text="🚤 ボート出港判定", bg="#0b4f6c", fg="white", font=("Yu Gothic UI", 18, "bold")).pack(pady=15)
        
        tk.Label(self.root, text="※相模川河口の潮位・潮汐・風速・風向・波高・うねりを総合評価", bg="#eef3f8", fg="#555555", font=("Yu Gothic UI", 9, "italic")).pack(pady=(5, 5))

        # 判定日選択
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        date_frame = tk.LabelFrame(self.root, text=" 判定日 ", bg="white", padx=10, pady=5)
        date_frame.pack(fill="x", padx=20, pady=5)
        
        # 選択可能な日付一覧を生成
        date_options = []
        # 日本時間の現在日付を取得
        JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
        today_jst = datetime.datetime.now(JST).date()

        for i in range(8):
            d = today_jst + datetime.timedelta(days=i)
            date_str = f"{d.strftime('%Y-%m-%d')}({weekdays[d.weekday()]})"
            date_options.append(date_str)
            
        self.date_combobox = ttk.Combobox(date_frame, values=date_options, state="readonly", width=20)
        self.date_combobox.set(date_options[0])
        self.date_combobox.pack(side=tk.LEFT, padx=5)

        # 判定基準表示
        # tk.Label(
        #     date_frame,
        #     text="【出港判定基準】: 潮位・潮汐・風速・風向・波高・うねりを総合評価",
        #     bg="white", fg="#c62828", font=("Yu Gothic UI", 9, "bold")
        # ).pack(side=tk.LEFT, padx=(15, 0))

        # 判定実行ボタン
        self.submit_btn = tk.Button(
            self.root, text="🔍 海況判定を実行する", command=self.on_click_check,
            bg="#0078D7", fg="white", font=("Yu Gothic UI", 12, "bold"), relief="flat", padx=25, pady=8, cursor="hand2"
        )
        self.submit_btn.pack(pady=12)

        # 総合判定表示
        status_panel = tk.Frame(self.root, bg="white", bd=1, relief="solid")
        status_panel.pack(fill="x", padx=20, pady=5)
        # tk.Label(status_panel, text="【 ボート出港判定 】", bg="white", fg="#666666", font=("Yu Gothic UI", 10, "bold")).pack(pady=(8, 0))

        self.result_label = tk.Label(status_panel, text="未判定", bg="white", fg="gray", font=("Yu Gothic UI", 26, "bold"))
        self.result_label.pack()
        self.weather_label = tk.Label(status_panel, text="", bg="white", fg="#0b4f6c", font=("Yu Gothic UI", 11, "bold"))
        self.weather_label.pack(pady=2)
        self.summary_label = tk.Label(status_panel, text="", bg="white", font=("Yu Gothic UI", 10), justify="center")
        self.summary_label.pack(pady=(2, 8))

        # 潮汐・天文情報表示
        self.tide_info_label = tk.Label(self.root, text="", bg="#eef3f8", fg="#444444", font=("Yu Gothic UI", 9, "bold"))
        self.tide_info_label.pack(pady=2)

        # 時間別判定一覧
        table_container = tk.Frame(self.root)
        table_container.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        COLUMNS = ("time", "status", "direction", "wind", "wave", "tide")
        TABLE_HEADERS = {
            "time": "時間",
            "status": "判定",
            "direction": "風向",
            "wind": "風速",
            "wave": "波浪",
            "tide": "潮位"
        }
        self.result_tree = ttk.Treeview(table_container, columns=COLUMNS, show="headings", height=12)
        for col_key, header_title in TABLE_HEADERS.items():
            self.result_tree.heading(col_key, text=header_title)
            self.result_tree.column(col_key, width=135, anchor="center", stretch=True)

        tree_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=tree_scroll.set)

        # 判定結果ごとの表示色
        self.result_tree.tag_configure("safe", background="#e8f5e9")
        self.result_tree.tag_configure("danger", background="#ffebee")
        self.result_tree.tag_configure("tide_low", background="#fff8e1")

        self.result_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    def on_click_check(self) -> None:
        """判定ボタン押下時のイベント: 非同期処理を開始する"""
        raw_date_str = self.date_combobox.get()
        if not raw_date_str:
            messagebox.showwarning("警告", "日付を選択してください。")
            return

        target_date_str = raw_date_str[:10]
        
        # 実行中は入力を一時的に無効化
        self.submit_btn.config(state=tk.DISABLED, text="⏳ 解析処理中...")
        self.weather_label.config(text="")
        self.summary_label.config(text="")
        self.tide_info_label.config(text="")
        self.result_label.config(text="データオンライン取得中...", fg="orange")
        for item in self.result_tree.get_children(): self.result_tree.delete(item)
        
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(self._async_fetch_and_judge, target_date_str, target_date)

    def _async_fetch_and_judge(self, target_date_str: str, target_date: datetime.date) -> None:
        """バックグラウンドで気象・潮汐データを取得し判定を計算する"""
        try:
            # サービス層は AnalysisResult クラスを1つだけ返します
            result = BoatDataService.get_full_analysis(target_date)

            # UI更新に AnalysisResult オブジェクトを丸ごと渡します
            # ※ _sync_render_ui 側も引数を1つ（result）受け取るように修正する必要があります
            self.root.after(0, self._sync_render_ui, result)
            
        except Exception as e:
            logger.error(f"非同期データ処理タスクに異常障害を検知: {e}")
            # ラムダ式を安全な形式に修正
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self._handle_async_error(msg))

    def _sync_render_ui(self, result: AnalysisResult) -> None:
        """
        データ分析結果オブジェクト(result)からUIコンポーネントを更新する。
        """
        self.submit_btn.config(state=tk.DISABLED, text="取得・解析中...")
        
        try:
            # データの検証
            if not result or not result.weather_info:
                messagebox.showerror("エラー", "気象データの取得または解析に失敗しました。")
                self.result_label.config(text="未判定(通信エラー)", fg="gray")
                return

            # --- AnalysisResult から各コンポーネントへ展開 ---
            weather_info = result.weather_info
            umi_info = result.umi_info
            hour_data = result.hour_data
            summary = result.summary

            # --- 天気サマリー ---
            daytime_summary = summarize_daytime_weather(
                weather_info.weather_code, 
                weather_info.precipitation_probability
            )
            self.weather_label.config(text=f"{daytime_summary} | 【{weather_info.temp_max:.0f}℃ / {weather_info.temp_min:.0f}℃】")

            # --- テーブル更新 ---
            self.result_tree.delete(*self.result_tree.get_children())
            
            # 日出・日入の取得 (エンジン層の機能を利用)
            sunrise_hour, sunset_hour = SunCalculator.get_sun_times(umi_info)
            
            table_rows = SafetyReportFormatter.build_table_rows(
                hour_data, sunrise_hour, sunset_hour
            )

            display_rows = ReportFormatter.build_display_rows(table_rows)

            for row in display_rows:
                self.result_tree.insert(
                    "", "end",
                    values=(
                        row.time_range, 
                        row.status, 
                        row.direction, 
                        row.wind, 
                        row.wave, 
                        row.tide
                    ),
                    tags=(row.tag,)
                )

            # --- 総合判定の表示 ---
            ui_data = SafetyReportFormatter.get_ui_summary_data(summary)
            self.result_label.config(text=f" {ui_data['label']}", fg=ui_data['color'])
            self.summary_label.config(text=ui_data['text'], fg=ui_data['color'])

            # --- 潮汐情報表示 ---
            self.tide_info_label.config(text=TideFormatter.get_ui_tide_text(umi_info))
            
        finally:
            self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")

    def _handle_async_error(self, err_msg: str) -> None:
        """非同期処理中のエラー発生時のダイアログ表示"""
        self.submit_btn.config(state=tk.NORMAL, text="🔍 海況判定を実行する")
        self.result_label.config(text="未判定(通信・内部エラー)", fg="gray")
        messagebox.showerror("致命的エラー", f"非同期判定タスクの駆動中にエラーが検出されました:\n{err_msg}")


def run_boat_desktop():
    """デスクトップ版アプリを起動する関数"""
    main_window = tk.Tk()
    app = BoatSafetyApp(main_window)
    main_window.mainloop()

if __name__ == "__main__":
    run_boat_desktop()