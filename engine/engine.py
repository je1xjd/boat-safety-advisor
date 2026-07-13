"""
engine.py

ボートの安全運航を判定するメインエンジン。
物理的限界値および運用ルールに基づき、海況ステータスを算出する。
"""

from .models import UmiInfo, HourForecast, AnalysisResult, AnalysisSummary
from .rules import SafetyRule
from .tide import TideJudge
from .wave import WaveJudge
from .evaluators import WindWaveEvaluator

class BoatSafetyEngine:
    """相模川河口海域における固有の気象・海象リスクを多角的に評価する判定エンジン。"""
    
    @classmethod
    def judge_wind_wave_only(
        cls, hour: int, wind_speed: float | None, wind_dir: float | None,
        wave_height: float | None, swell_period: float | None,
        high_tides: list[int], low_tides: list[int]
    ) -> bool:
        """風速・風向・沿岸波浪・うねり条件に基づき単独判定する。"""
        from engine.wind import WindJudge

        if any(v is None for v in [wind_speed, wind_dir, wave_height, swell_period]):
            return False

        if not WaveJudge.is_physically_safe(wave_height, swell_period):
            return False
        if not WaveJudge.is_complex_safe(wave_height, swell_period):
            return False

        is_south = WindJudge.is_south_wind(wind_dir)
        is_ebb = TideJudge.is_ebbing_tide(hour, high_tides, low_tides)
        
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        
        limit = WindJudge.get_limit(is_ebb, is_south, wave_height <= limit_wave)
        return WindJudge.is_safe(wind_speed, limit, wave_height)

    @classmethod
    def judge_safety(cls, hour, wind_speed, wind_dir, wave_height, swell_period, tide_val, high_tides, low_tides) -> bool:
        """指定された気象・海象条件における航行の安全性を判定する。"""
        is_ebb = TideJudge.is_ebbing_tide(hour, high_tides, low_tides)
        
        wind_wave_ok = WindWaveEvaluator.judge(
            hour, wind_speed, wind_dir, wave_height, swell_period, is_ebb
        )
        
        tide_safe = TideJudge.is_tide_safe(tide_val)
        
        return wind_wave_ok and tide_safe

    @classmethod
    def calculate_valid_windows(cls, hour_data: dict) -> tuple[list, list, list]:
        """航行可能な時間帯の候補を算出し、潮位による制約でフィルタリングする。"""
        valid_windows = []
        
        for start_hour in range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR):
            for end_hour in range(start_hour + SafetyRule.REQUIRED_SAFE_HOURS - 1, SafetyRule.ACTIVITY_END_HOUR):

                if not (hour_data[start_hour].is_safe and hour_data[end_hour].is_safe):
                            continue

                all_navigable = True
                
                for h in range(start_hour, end_hour + 1):
                    is_ok = h in hour_data and hour_data[h].is_navigable
                    if not is_ok:
                        all_navigable = False
                        break
                
                if all_navigable:
                    duration = end_hour - start_hour + 1
                    valid_windows.append((start_hour, end_hour + 1, duration))
        
        low_hours = [h for h, data in hour_data.items() if data.is_tide_low()]
    
        if low_hours:
            first_low = min(low_hours)
            last_low = max(low_hours)
            before_candidates = [w for w in valid_windows if w[1] <= first_low]
            after_candidates = [w for w in valid_windows if w[0] > last_low]
        else:
            before_candidates = valid_windows
            after_candidates = []

        return valid_windows, before_candidates, after_candidates

    @classmethod
    def get_display_status(cls, hour: int, data: object, sunrise_hour: int, sunset_hour: int) -> tuple[str, str]:
        """UI表示用の海況ステータスとカラーカテゴリを返す。"""
        if not (sunrise_hour <= hour < sunset_hour):
            return ("日没" if hour >= sunset_hour else "夜明"), "danger"

        if data.is_safe:
            return "安全", "safe"
        
        if getattr(data, 'is_tide_warning', False):
            return "潮位", "tide_low"
            
        return "危険", "danger"

    @classmethod
    def build_before_after_summary(
        cls,
        before_candidates: list,
        after_candidates: list
    ) -> tuple[str, str]:
        """潮位低下前後の最適航行時間を要約する。"""
        before_str = "該当なし"

        if before_candidates:
            best_b = max(before_candidates, key=lambda x: x[2])
            before_str = f"{best_b[0]:02d}-{best_b[1]:02d}時"

        after_str = "該当なし"

        if after_candidates:
            best_a = max(after_candidates, key=lambda x: x[2])
            after_str = f"{best_a[0]:02d}-{best_a[1]:02d}時"

        return before_str, after_str

    @classmethod
    def get_best_window(
        cls,
        valid_windows: list
    ) -> tuple:
        """航行可能な時間帯のうち、最も長い期間を返す。"""
        if not valid_windows:
            return (0, 0, 0)

        return max(valid_windows, key=lambda x: x[2])

    @staticmethod
    def get_ui_tide_text(umi: UmiInfo) -> str:
        """UI表示用の潮汐・月齢・日出入情報文字列を生成する。"""
        return (f"🌀 {umi.tide_name} "
                f"(満潮 {umi.high_tide} ／ 干潮 {umi.low_tide})   "
                f"🌗 月齢: {umi.moon_age}   "
                f"🌅 日出: {umi.sun_rise} ／ 日入: {umi.sun_set}")

    @classmethod
    def apply_sequence_rules(cls, hour_data: dict, sunrise_hour: int, sunset_hour: int):
        """時間帯ごとの物理的安全性と潮位低下によるリスクをシーケンスで判定する。"""
        hours = sorted(hour_data.keys())
        
        for hour in hours:
            data = hour_data[hour]
            is_time_ok = (sunrise_hour <= hour < sunset_hour)
            data.is_safe = is_time_ok and data.wind_wave_safe
            data.is_tide_warning = False

        i = 0
        while i < len(hours):
            if hour_data[hours[i]].is_tide_low():
                start = i
                while i < len(hours) and hour_data[hours[i]].is_tide_low():
                    i += 1
                end = i - 1
                
                # 潮位低下期間の前後が安全な場合のみ、黄色（注意）として扱う
                prev_h = hours[start - 1] if start > 0 else None
                next_h = hours[end + 1] if end < len(hours) - 1 else None
                
                prev_safe = (prev_h is not None and hour_data[prev_h].is_safe)
                next_safe = (next_h is not None and hour_data[next_h].is_safe)
                
                if prev_safe and next_safe:
                    for idx in range(start, end + 1):
                        hour_data[hours[idx]].is_tide_warning = True
                        hour_data[hours[idx]].is_safe = False
                else:
                    for idx in range(start, end + 1):
                        hour_data[hours[idx]].is_safe = False
            else:
                i += 1

