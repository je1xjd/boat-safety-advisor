"""
models.py

ボートの安全判定システムで使用するデータ構造の定義。
"""

from dataclasses import dataclass
from typing import List, Optional
from engine.rules import SafetyRule

@dataclass
class UmiInfo:
    """潮汐・月齢・日出入情報。"""
    tide_name: str = "不明"
    high_tide: str = "--"
    low_tide: str = "--"
    moon_age: str = "--"
    sun_rise: str = "--"
    sun_set: str = "--"

@dataclass
class WeatherReport:
    """気象・海象データのコンテナ。"""
    times: list[str]
    wind_speed: list[float | None]
    wind_direction: list[float | None]
    wave_height: list[float | None]
    swell_period: list[float | None]
    precipitation_probability: list[int]
    weather_code: list[int | None]
    daily_weather_code: int | None
    temp_max: float
    temp_min: float

@dataclass
class HourForecast:
    """1時間ごとの気象・海象および安全性判定結果を保持する。"""
    wind_speed: float | None
    wind_dir: float | None
    wave_height: float | None
    swell_period: float | None
    tide: float | None
    wind_wave_safe: bool = False
    is_safe: bool = False
    is_navigable: bool = False
    dir_kanji: str = "不明"
    is_tide_warning: bool = False

    def get_status_tag(self) -> str:
        """ステータスに応じたUIタグを返す。"""
        if self.is_safe:
            return "safe"
        if self.is_tide_low():
            return "tide_low"
        return "danger"

    def is_tide_low(self) -> bool:
        """現在の潮位が航行基準値未満か判定する。"""
        return (self.tide or 0) < SafetyRule.MIN_TIDE_CM

@dataclass(frozen=True)
class AnalysisSummary:
    """1日分の航行可能時間帯に関する総合判定サマリー。"""
    is_available: bool
    best_window: tuple[int, int, int]
    before_str: str
    after_str: str

@dataclass(frozen=True)
class AnalysisResult:
    """解析プロセス全体の結果一式。"""
    hour_data: dict
    summary: AnalysisSummary
    weather_info: WeatherReport
    umi_info: UmiInfo
