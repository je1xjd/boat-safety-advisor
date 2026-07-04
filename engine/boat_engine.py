import logging
from engine.models import HourForecast, UmiInfo, AnalysisResult, AnalysisSummary
from engine.rules import SafetyRule

# もし必要であれば、以下のように分割後の各ロジックを読み込む形にします
# from engine.wind import WindJudge
# from engine.wave import WaveJudge
# from engine.tide import TideJudge
# from engine.navigation import NavigationAnalyzer

# ログ設定
logger = logging.getLogger(__name__)


# ==============================================================================
# 航行安全判定エンジン
# ==============================================================================

class WindJudge:
    """風に関する判定を専門に行うクラス"""

    @staticmethod
    def is_south_wind(wind_dir: float) -> bool:
        return SafetyRule.SOUTH_WIND_START <= wind_dir <= SafetyRule.SOUTH_WIND_END

    @staticmethod
    def get_limit(is_ebb: bool, is_south: bool, is_under_operational_limit: bool) -> float:
        if is_ebb and is_south:
            return SafetyRule.WIND_LIMIT_CRITICAL
        if is_ebb or is_south or not is_under_operational_limit:
            return SafetyRule.WIND_LIMIT_EBB
        return SafetyRule.WIND_LIMIT_NORMAL

    @staticmethod
    def is_safe(wind_speed: float, limit: float, wave_height: float) -> bool:
        # 風速上限判定
        if wind_speed > limit:
            # 例外許可判定
            if (
                wind_speed <= (limit + SafetyRule.WIND_OVERRIDE_MARGIN)
                and wave_height < SafetyRule.WIND_OVERRIDE_WAVE_HEIGHT
            ):
                return True
            return False
        return True

class WaveJudge:
    """波やうねりに関する判定ロジックを担当するクラス"""

    @staticmethod
    def is_physically_safe(wave_height: float, swell_period: float) -> bool:
        """物理的限界判定：波高と周期が限界値を超えていないか"""
        return (
            wave_height <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL 
            and swell_period < SafetyRule.MAX_SWELL_PERIOD
        )

    @staticmethod
    def is_complex_safe(wave_height: float, swell_period: float) -> bool:
        """複合危険判定：うねりと波高の組み合わせによる危険性"""
        return not (
            swell_period >= SafetyRule.MAX_COMBINED_SWELL_PERIOD 
            and wave_height >= SafetyRule.MAX_COMBINED_WAVE_HEIGHT
        )

class TideJudge:
    """潮汐・潮位に関する判定ロジックを担当するクラス"""

    @staticmethod
    def is_tide_safe(tide_cm: float | None) -> bool:
        """潮位が安全基準を満たしているか"""
        if tide_cm is None:
            return False
        return tide_cm >= SafetyRule.MIN_TIDE_CM

    @staticmethod
    def is_tide_low(tide_cm: float | None) -> bool:
        """潮位が基準を下回っている（注意が必要な）状態か"""
        if tide_cm is None:
            return False
        return tide_cm < SafetyRule.MIN_TIDE_CM


class SunCalculator:
    """日出・日入時刻の抽出と管理を行うクラス"""

    @classmethod
    def get_sun_times(cls, umi: 'UmiInfo') -> tuple[int, int]:
        """UmiInfoから日出・日入時刻を抽出し、時間(int)のタプルで返す"""
        sunrise_hour = -1
        sunset_hour = 25

        if umi.sun_rise != "－－" and umi.sun_set != "－－":
            try:
                sunrise_hour = int(umi.sun_rise.split(":")[0])
                sunset_hour = int(umi.sun_set.split(":")[0])
            except (ValueError, AttributeError):
                # 予期せぬフォーマットの場合はデフォルト値を保持
                pass

        return sunrise_hour, sunset_hour




class WindWaveEvaluator:
    """風と波の判定ロジックを専門に扱うクラス"""

    @staticmethod
    def judge(hour: int, wind_speed: float | None, wind_dir: float | None,
              wave_height: float | None, swell_period: float | None,
              high_tides: list[int], low_tides: list[int]) -> bool:

        if wind_speed is None or wind_dir is None or wave_height is None or swell_period is None:
            return False

        # 1. 波・うねりの物理判定
        if not WaveJudge.is_physically_safe(wave_height, swell_period):
            return False

        # 2. 複合危険判定
        if not WaveJudge.is_complex_safe(wave_height, swell_period):
            return False

        # 3. 運用制約・風速判定
        is_south = WindJudge.is_south_wind(wind_dir)
        # BoatSafetyEngineに残っている is_ebbing_tide を呼び出す
        is_ebb = BoatSafetyEngine.is_ebbing_tide(hour, high_tides, low_tides)
        
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        is_under_operational_limit = wave_height <= limit_wave

        limit = WindJudge.get_limit(is_ebb, is_south, is_under_operational_limit)
        
        return WindJudge.is_safe(wind_speed, limit, wave_height)





# ==============================================================================
# 表示用データ生成
# ==============================================================================

def summarize_daytime_weather(weather_codes: list[int], precip_probs: list[int]) -> str:
    """07〜18時の予報を午前・午後に分けて要約表示する"""

    # weather_mapping = {
    #     0: "快晴", 1: "晴れ", 2: "晴れ時々曇り", 3: "曇り", 45: "霧",
    #     48: "濃霧", 51: "霧雨", 53: "小雨", 55: "雨", 61: "雨",
    #     63: "強い雨", 65: "豪雨", 80: "にわか雨", 95: "雷雨"
    # }


    if not weather_codes or len(weather_codes) < 19 or not precip_probs:
        return "－"

# 天気アイコンのマッピング
    weather_mapping = {
        0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️",
        48: "🌫️", 51: "🌦️", 53: "🌧️", 55: "🌧️", 61: "🌧️",
        63: "🌧️", 65: "⛈️", 80: "🌦️", 95: "⚡"
    }

    MORNING_RANGE = (7, 13)
    AFTERNOON_RANGE = (13, 19)

    def get_period_summary(start: int, end: int):
        # 指定範囲のデータを抽出
        period_codes = weather_codes[start:end]
        period_probs = precip_probs[start:end]
        
        # 代表天気（最頻値）
        main_weather = weather_mapping.get(max(set(period_codes), key=period_codes.count), "☁️")
        
        # 降水確率の最大値（Max値を10%単位に四捨五入）
        avg_value = sum(period_probs) / len(period_probs)
        avg_precip = round(avg_value / 10) * 10
        
        return f"{main_weather} {avg_precip}%"

    # 午前と午後の要約を結合
    return f"【{get_period_summary(*MORNING_RANGE)}/{get_period_summary(*AFTERNOON_RANGE)}】"
