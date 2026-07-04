from dataclasses import dataclass
from typing import List, Optional
from engine.rules import SafetyRule

@dataclass
class UmiInfo:
    tide_name: str = "不明"
    high_tide: str = "--"
    low_tide: str = "--"
    moon_age: str = "--"
    sun_rise: str = "--"
    sun_set: str = "--"

@dataclass
class WeatherReport:
    """気象・海象データの型付きコンテナ"""
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
    """1時間ごとの気象・海象・判定結果を保持するクラス"""
    wind_speed: float | None
    wind_dir: float | None
    wave_height: float | None
    swell_period: float | None
    tide: float | None
    wind_wave_safe: bool = False
    is_safe: bool = False
    is_navigable: bool = False
    dir_kanji: str = "不明"

    def get_status_tag(self) -> str:
        """この時間帯のステータスを判定してタグを返す"""
        if self.is_safe:
            return "safe"
        if self.is_tide_low():
            return "tide_low"
        return "danger"

    def is_tide_low(self) -> bool:
        """潮位が基準値未満か判定する"""
        return self.tide is not None and self.tide < SafetyRule.MIN_TIDE_CM

@dataclass(frozen=True)
class AnalysisSummary:
    """総合判定結果を保持するデータクラス"""
    is_available: bool
    best_window: tuple  # (start, end, duration)
    before_str: str
    after_str: str

@dataclass(frozen=True)
class AnalysisResult:
    """1日分の解析結果一式を保持するデータクラス"""
    hour_data: dict  # または List[HourForecast] に近い将来変更可能
    summary: AnalysisSummary
    weather_info: WeatherReport
    umi_info: UmiInfo




