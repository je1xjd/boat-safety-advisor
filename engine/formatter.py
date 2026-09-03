"""
formatter.py

各種判定結果および生データを、UI表示に適した形式へ整形する。
"""

import datetime
import logging
from dataclasses import dataclass

from engine.engine import BoatSafetyEngine
from engine.rules import SafetyRule

logger = logging.getLogger(__name__)


class StatusUIConfig:
    """判定ステータスに応じた表示スタイルとラベルを管理する。"""

    MAPPING = {
        "safe": {"color": "#1a7f37", "label": "出港可能"},
        "danger": {"color": "#c62828", "label": "出港不可"},
    }

    @staticmethod
    def get_style(status: str) -> dict:
        """指定されたステータスに対するスタイル設定を返す。"""
        target = "danger" if status == "tide_low" else status
        return StatusUIConfig.MAPPING.get(target, {"color": "#000000", "label": "不明"})


class TideFormatter:
    """潮汐情報の表示用テキスト整形を行う。"""

    @staticmethod
    def get_ui_tide_text(umi_info) -> str:
        """潮汐情報をUI表示用の文字列にフォーマットする。"""
        if not umi_info or umi_info.tide_name == "不明":
            return "潮汐情報: 取得失敗"
        return (
            f"🌀 {umi_info.tide_name} "
            f"(満潮 {umi_info.high_tide} ／ 干潮 {umi_info.low_tide})   "
            f"🌗 月齢: {umi_info.moon_age}   "
            f"🌅 日出: {umi_info.sun_rise} ／ 日入: {umi_info.sun_set}"
        )


class StatusFormatter:
    """判定結果をUI表示用スタイル（背景色）へ変換する。"""

    @staticmethod
    def get_status_color(status_text: str) -> str:
        """判定文字列から対応する背景色を返す。"""
        if any(kw in status_text for kw in ["危険", "不可", "夜明", "日没"]):
            return "#f8d7da"
        if any(kw in status_text for kw in ["注意", "潮位"]):
            return "#fff3cd"
        if "安全" in status_text:
            return "#d4edda"
        return "#ffffff"


class SafetyReportFormatter:
    """分析サマリーおよび時系列データの整形を担当する。"""

    @staticmethod
    def get_ui_summary_data(summary: "AnalysisSummary") -> dict:
        """判定サマリーからUI用のラベルとスタイル情報を生成する。"""
        is_available = summary.is_available
        status = "safe" if is_available else "danger"
        style = StatusUIConfig.get_style(status)

        text = SafetyReportFormatter.build_summary_text(summary)

        return {"text": text, "label": style["label"], "color": style["color"]}

    @classmethod
    def build_table_rows(
        cls,
        hour_data: dict,
        sunrise_time: datetime.time | None,
        sunset_time: datetime.time | None,
    ) -> list:
        """気象データに基づき、テーブル表示用の行データを生成する。"""
        BoatSafetyEngine.apply_sequence_rules(hour_data, sunrise_time, sunset_time)

        rows = []
        for hour in sorted(hour_data.keys()):
            rows.append(
                cls._format_row(hour, hour_data[hour], sunrise_time, sunset_time)
            )
        return rows

    @staticmethod
    def _format_row(
        hour: int,
        data: object,
        sunrise_time: datetime.time | None,
        sunset_time: datetime.time | None,
    ) -> dict:
        """単一時間帯のデータをUI表示用辞書に整形する。"""
        status, tag = BoatSafetyEngine.get_display_status(
            hour, data, sunrise_time, sunset_time
        )

        wind_text = (
            f"{data.wind_speed:.1f}m/s"
            if getattr(data, "wind_speed", None) is not None
            else "取得失敗"
        )
        wave_text = (
            f"{data.wave_height:.2f}m"
            if getattr(data, "wave_height", None) is not None
            else "取得失敗"
        )
        swell_text = (
            f"{getattr(data, 'swell_period', getattr(data, 'swell', None)):.1f}s"
            if getattr(data, 'swell_period', getattr(data, 'swell', None)) is not None
            else "取得失敗"
        )
        tide_text = (
            f"{int(data.tide)}cm"
            if getattr(data, "tide", None) is not None
            else "取得失敗"
        )

        precip_val = getattr(data, "precipitation_probability", getattr(data, "precip_prob", None))
        precip_text = (
            f"{round(precip_val, -1):.0f}%"
            if precip_val is not None
            else "取得失敗"
        )

        temp_val = getattr(data, "temperature", getattr(data, "temp", None))
        temp_text = (
            f"{temp_val:.1f}℃" if temp_val is not None else "取得失敗"
        )

        return {
            "hour": hour,
            "status": status,
            "tag": tag,
            "direction": getattr(data, "dir_kanji", "-"),
            "wind_text": wind_text,
            "wave_text": wave_text,
            "swell_text": swell_text,
            "tide_text": tide_text,
            "precip_text": precip_text,
            "temp_text": temp_text,
        }


    @staticmethod
    def build_summary_text(summary: dict) -> str:
        """総合判定結果から要約テキストを生成する。"""
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
    """テーブル表示用の行データモデル。"""

    time_range: str
    status: str
    direction: str
    wind: str
    wave: str
    swell: str
    tide: str
    precip: str
    temp: str
    tag: str


class ReportFormatter:
    """UI表示用整形クラス。"""

    @staticmethod
    def build_display_rows(table_rows: list) -> list[UIRow]:
        """辞書リストをUIRowオブジェクトのリストへ変換する。"""
        return [
            UIRow(
                time_range=f"{r['hour']:02d}",
                status=r["status"],
                direction=r["direction"],
                wind=r["wind_text"],
                wave=r["wave_text"],
                swell=r["swell_text"],
                tide=r["tide_text"],
                precip=r["precip_text"],
                temp=r["temp_text"],
                tag=r.get("tag", "normal"),
            )
            for r in table_rows
        ]

    @staticmethod
    def filter_display_rows(rows: list[UIRow]) -> list[UIRow]:
        """18時までのデータのみに絞り込む。"""
        return [
            row
            for row in rows
            if int(row.time_range.split("-")[0]) <= SafetyRule.ACTIVITY_END_HOUR
        ]
