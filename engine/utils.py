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

