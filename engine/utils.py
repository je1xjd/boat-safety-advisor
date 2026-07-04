# ==============================================================================
# 表示用データ生成
# ==============================================================================

WEATHER_MAPPING = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️",
    48: "🌫️", 51: "🌦️", 53: "🌧️", 55: "🌧️", 61: "🌧️",
    63: "🌧️", 65: "⛈️", 80: "🌦️", 95: "⚡"
}

def summarize_daytime_weather(weather_codes: list[int], precip_probs: list[int]) -> str:
    """07〜18時の予報を午前・午後に分けて要約する"""

    if not weather_codes or len(weather_codes) < 19 or not precip_probs:
        return "－"

    MORNING_RANGE = (7, 13)
    AFTERNOON_RANGE = (13, 19)

    def get_period_summary(start: int, end: int) -> str:
        period_codes = weather_codes[start:end]
        period_probs = precip_probs[start:end]
        
        # 最頻値を代表天気とする
        main_weather = WEATHER_MAPPING.get(max(set(period_codes), key=period_codes.count), "☁️")
        
        # 降水確率の平均を10%単位に四捨五入
        avg_precip = round((sum(period_probs) / len(period_probs)) / 10) * 10
        
        return f"{main_weather} {avg_precip}%"

    return f"【{get_period_summary(*MORNING_RANGE)}/{get_period_summary(*AFTERNOON_RANGE)}】"

class SunCalculator:
    """日出・日入時刻の抽出と管理を行うクラス"""

    @classmethod
    def get_sun_times(cls, umi: 'UmiInfo') -> tuple[int, int]:
        """UmiInfoから日出・日入時刻を抽出し、時間(int)のタプルを返す"""
        sunrise_hour, sunset_hour = -1, 25

        if umi.sun_rise != "－－" and umi.sun_set != "－－":
            try:
                sunrise_hour = int(umi.sun_rise.split(":")[0])
                sunset_hour = int(umi.sun_set.split(":")[0])
            except (ValueError, AttributeError):
                pass

        return sunrise_hour, sunset_hour
