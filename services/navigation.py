"""
navigation.py

気象・海象データから航行分析に必要なデータ構造を組み立てる。
"""

from .models import HourForecast, AnalysisSummary
from .rules import SafetyRule
from .tide import TideJudge
from .wind import WindJudge
from .engine import BoatSafetyEngine

class NavigationAnalyzer:
    """気象・海象データおよび判定結果を統合し、分析用データ構造を生成する。"""

    @classmethod
    def build_hour_data(
        cls,
        weather_info: dict,
        tide_data: list,
        high_tides: list[int],
        low_tides: list[int]
    ) -> dict:
        """気象・潮汐情報から1時間ごとの航行可否データを生成する。"""

        max_len = min(
            len(weather_info.wind_speed),
            len(weather_info.wind_direction),
            len(weather_info.wave_height),
            len(weather_info.swell_period)
        )

        hour_data = {}

        for hour in range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.FETCH_END_HOUR):
            if hour >= max_len or hour >= len(tide_data):
                continue

            # 1時間ごとのデータを抽出・判定して格納
            hour_data[hour] = cls._build_single_hour_forecast(
                hour, weather_info, tide_data, high_tides, low_tides
            )

        return hour_data

    @classmethod
    def _build_single_hour_forecast(
        cls,
        hour: int,
        weather_info: dict,
        tide_data: list,
        high_tides: list[int],
        low_tides: list[int]
    ) -> HourForecast:
        """指定された1時間分の気象・潮汐データを取得し、判定結果を含むForecastオブジェクトを生成する。"""
        wind_speed = weather_info.wind_speed[hour]
        wind_dir = weather_info.wind_direction[hour]
        wave_height = weather_info.wave_height[hour]
        swell_period = weather_info.swell_period[hour]
        tide_val = tide_data[hour]

        wind_wave_ok = BoatSafetyEngine.judge_wind_wave_only(
            hour, wind_speed, wind_dir, wave_height, swell_period, high_tides, low_tides
        )

        total_ok = BoatSafetyEngine.judge_safety(
            hour,
            wind_speed,
            wind_dir,
            wave_height,
            swell_period,
            tide_val,
            high_tides,
            low_tides
        )

        is_navigable = (
            total_ok
            or (
                wind_wave_ok
                and TideJudge.is_tide_low(tide_val)
            )
        )

        return HourForecast(
            wind_speed=wind_speed,
            wind_dir=wind_dir,
            wave_height=wave_height,
            swell_period=swell_period,
            tide=tide_val,
            wind_wave_safe=wind_wave_ok,
            is_safe=total_ok,
            is_navigable=is_navigable,
            dir_kanji=WindJudge.degrees_to_direction(wind_dir)
        )

    @classmethod
    def build_navigation_summary(cls, hour_data) -> AnalysisSummary:
        """航行可能な時間帯を抽出し、総合的な分析サマリーを作成する。[cite: 4]"""

        valid_windows, before_c, after_c = (
            BoatSafetyEngine.calculate_valid_windows(hour_data)
        )

        before_str, after_str = (
            BoatSafetyEngine.build_before_after_summary(
                before_c,
                after_c
            )
        )

        best_window = BoatSafetyEngine.get_best_window(
            valid_windows
        )

        is_available = len(valid_windows) > 0

        return AnalysisSummary(
            is_available=is_available,
            best_window=best_window,
            before_str=before_str,
            after_str=after_str
        )
