import logging
from dataclasses import dataclass

# 新しいエンジン層からインポート
from engine.models import HourForecast
from engine.rules import SafetyRule
from engine.engine import BoatSafetyEngine

# 既存のロガー設定など
logger = logging.getLogger(__name__)


# ==============================================================================
# UI共通スタイル定義 
# ==============================================================================
class StatusUIConfig:
    """判定ステータスごとの表示スタイルを管理する設定クラス"""
    MAPPING = {
        "safe":     {"color": "#1a7f37", "label": "出港可能"},
        "danger":   {"color": "#c62828", "label": "出港不可"}
    }

    @staticmethod
    def get_style(status: str) -> dict:
        """ステータスに応じたスタイル情報を取得。tide_lowはdangerに統合"""
        # tide_low は正規化により danger に統合されるため、定義から除外して危険として扱う
        if status == "tide_low":
            return StatusUIConfig.MAPPING["danger"]
        return StatusUIConfig.MAPPING.get(status, {"color": "#000000", "label": "不明"})

class TideFormatter:
    """潮汐情報の表示用テキスト整形"""

    @staticmethod
    def get_ui_tide_text(umi_info) -> str:
        """潮汐情報をUI表示用にフォーマットする"""
        if not umi_info or umi_info.tide_name == "不明":
            return "潮汐情報: 取得失敗"
        return (f"🌀 {umi_info.tide_name} "
                f"(満潮 {umi_info.high_tide} ／ 干潮 {umi_info.low_tide})   "
                f"🌗 月齢: {umi_info.moon_age}   "
                f"🌅 日出: {umi_info.sun_rise} ／ 日入: {umi_info.sun_set}")



class StatusFormatter:
    """判定結果をUI表示用に変換する（エンジンから移管）"""
    
    @staticmethod
    def get_status_color(status_text: str) -> str:
        """判定文字列から対応する背景色を返す共通ロジック"""
        if any(kw in status_text for kw in ["危険", "不可"]):
            return "#f8d7da"  # 赤系
        if any(kw in status_text for kw in ["注意", "潮位", "夜明", "日没"]):
            return "#fff3cd"  # 黄系
        if "安全" in status_text:
            return "#d4edda"  # 緑系
        return "#ffffff"      # デフォルト白




# ==============================================================================
# UI表示用の整形を担当するクラス
# ==============================================================================
class SafetyReportFormatter:

    @staticmethod
    def get_ui_summary_data(summary: "AnalysisSummary") -> dict:
        """
        判定結果から、UI表示に必要なラベルとスタイル情報を一括生成する。
        これにより、UI側の条件分岐（if/else）を排除する。
        """
        # クラスの属性に直接アクセス（.get は不要）
        is_available = summary.is_available
        status = "safe" if is_available else "danger"
        style = StatusUIConfig.get_style(status)
        
        # 既存のテキスト生成ロジックを流用（引数はクラスのまま渡す）
        text = SafetyReportFormatter.build_summary_text(summary)
        
        return {
            "text": text,
            "label": style["label"],
            "color": style["color"]
        }

    @classmethod
    def build_table_rows(
        cls,
        hour_data: dict,
        sunrise_hour: int,
        sunset_hour: int
    ) -> list:
        
        # 1. 潮位低下などの特殊ルールを適用して、HourForecast のフラグを更新
        # ※Engine側で hour_data を直接操作（is_safe = False などに書き換え）する形にします
        BoatSafetyEngine.apply_sequence_rules(hour_data, sunrise_hour, sunset_hour)

        # 2. 表示行生成（判定済みデータを使うだけ！）
        rows = []
        # 時間順にソートして処理
        for hour in sorted(hour_data.keys()):
            # 【修正点】ここで sunrise_hour と sunset_hour を渡す
            rows.append(cls._format_row(hour, hour_data[hour], sunrise_hour, sunset_hour))
        return rows

    @staticmethod
    def _format_row(hour: int, data: object, sunrise_hour: int, sunset_hour: int) -> dict:
        """行ごとのデータ整形ヘルパー"""
        
        # ロジックを BoatSafetyEngine に委譲して一元化
        status, tag = BoatSafetyEngine.get_display_status(hour, data, sunrise_hour, sunset_hour)
        
        return {
            "hour": hour,
            "status": status,
            "tag": tag,
            "direction": data.dir_kanji,
            "wind_text": f"{data.wind_speed:.1f} m/s" if data.wind_speed is not None else "取得失敗",
            "wave_text": (
                f"{data.wave_height:.2f}m / {data.swell_period:.1f}s"
                if data.wave_height is not None and data.swell_period is not None
                else "取得失敗"
            ),
            "tide_text": f"{int(data.tide)} cm" if data.tide is not None else "取得失敗"
        }

    @staticmethod
    def build_summary_text(summary: dict) -> str:
        """
        総合判定結果から要約テキストを生成する
        """
        if not summary.is_available:
            return (
                f"連続して安全な時間帯が "
                f"{SafetyRule.REQUIRED_SAFE_HOURS} 時間以上確保できません。"
            )

        max_act = summary.best_window

        return (
            f"最大連続活動枠: "
            f"{max_act[0]:02d}-{max_act[1]:02d}時 "
            f"({max_act[2]}h) | "
            f" "
            f"[前半: {summary.before_str} / "
            f"後半: {summary.after_str}]"
        )


@dataclass
class UIRow:
    """テーブル表示用の行データを定義"""
    time_range: str
    status: str
    direction: str
    wind: str
    wave: str
    tide: str
    tag: str

class ReportFormatter:
    """UI表示整形専門のクラス"""

    @staticmethod
    def build_display_rows(table_rows: list) -> list[UIRow]:
        """dictリストをUIRowリストに変換"""
        rows = []
        for row in table_rows:
            # ここで全てのフィールドに値を割り当てます
            rows.append(UIRow(
                time_range=f"{row['hour']:02d}-{row['hour'] + 1:02d}",
                status=row["status"],
                direction=row["direction"],
                wind=row["wind_text"],
                wave=row["wave_text"],
                tide=row["tide_text"],
                tag=row.get("tag", "normal") # 安全のため get を使用
            ))
        return rows