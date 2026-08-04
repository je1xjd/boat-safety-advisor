"""
utils.py

UI表示用の気象要約および時間計算ユーティリティ。
"""

import datetime

# 絵文字と日本語名を紐付けた天気マッピング（3桁の天気コードに対応）
WEATHER_MAPPING = {
    0: {"emoji": "☀️", "name": "晴れ"},
    1: {"emoji": "🌤️", "name": "晴れ時々曇り"},
    2: {"emoji": "⛅", "name": "曇り時々晴れ"},
    3: {"emoji": "☁️", "name": "曇り"},
    45: {"emoji": "🌫️", "name": "霧"},
    48: {"emoji": "🌫️", "name": "霧氷"},
    51: {"emoji": "🌦️", "name": "小雨"},
    53: {"emoji": "🌧️", "name": "雨"},
    55: {"emoji": "🌧️", "name": "強い雨"},
    61: {"emoji": "🌧️", "name": "雨"},
    63: {"emoji": "🌧️", "name": "雨"},
    65: {"emoji": "⛈️", "name": "大雨・雷"},
    71: {"emoji": "🌨️", "name": "小雪"},
    73: {"emoji": "❄️", "name": "雪"},
    75: {"emoji": "❄️", "name": "大雪"},
    80: {"emoji": "🌦️", "name": "にわか雨"},
    85: {"emoji": "🌨️", "name": "にわか雪"},
    95: {"emoji": "⚡", "name": "雷雨"},
}


def summarize_daytime_weather(weather_codes: list[int], precip_probs: list[int]) -> str:
    """07〜18時の予報を集約し、自然な天気要約と、午前・午後の最大降水確率を生成する。"""

    if not weather_codes or len(weather_codes) < 19 or not precip_probs:
        return "--- | 【---% / ---%】"

    MORNING_RANGE = (7, 13)
    AFTERNOON_RANGE = (13, 19)

    def get_period_precip(start: int, end: int) -> float:
        """指定期間の降水確率の最大値を算出し、10%単位に丸める。"""
        period_probs = precip_probs[start:end]
        max_precip_val = max(period_probs)
        return round(max_precip_val, -1)

    def get_worst_weather_code(codes):
        """指定された時間内のコードから、安全管理上最も重要視すべき（荒れた）天気コードを選ぶ。"""
        if not codes:
            return 3  # デフォルト：曇り
        
        severe_codes = [95, 65, 55, 63, 61, 53, 51, 80, 75, 73, 71, 85]
        for severe in severe_codes:
            if severe in codes:
                return severe
                
        return max(codes)

    # 1. 前半（07〜13時）と後半（13〜19時）のコードを取得
    morning_codes = weather_codes[7:13]
    afternoon_codes = weather_codes[13:19]

    morning_main = get_worst_weather_code(morning_codes)
    afternoon_main = get_worst_weather_code(afternoon_codes)

    # 2. 「のち」と「時々」の混在を防ぐロジック
    if morning_main == afternoon_main:
        w_info = WEATHER_MAPPING.get(morning_main, {"emoji": "☁️", "name": "曇り"})
        weather_str = f"{w_info['emoji']} {w_info['name']}"
    else:
        def get_base_weather(code):
            if code in [0, 1]:
                return {"emoji": "☀️", "name": "晴れ"}
            elif code in [2, 3]:
                return {"emoji": "☁️", "name": "曇り"}
            elif code in [51, 53, 55, 61, 63, 80]:
                return {"emoji": "🌧️", "name": "雨"}
            elif code in [65, 95]:
                return {"emoji": "⛈️", "name": "雷雨"}
            elif code in [71, 73, 75, 85]:
                return {"emoji": "❄️", "name": "雪"}

        m_base = get_base_weather(morning_main)
        a_base = get_base_weather(afternoon_main)

        if m_base["name"] == a_base["name"]:
            weather_str = f"{m_base['emoji']} {m_base['name']}"
        else:
            weather_str = f"{m_base['emoji']} {m_base['name']}のち{a_base['name']}"

    # 3. 午前・午後の最大降水確率をそれぞれ算出
    morning_precip = get_period_precip(*MORNING_RANGE)
    afternoon_precip = get_period_precip(*AFTERNOON_RANGE)

    # 4. 天気 ｜ 【午前% / 午後%】 の形式で返す
    return f"{weather_str} | 【{morning_precip:.0f}% / {afternoon_precip:.0f}%】"


class SunCalculator:
    """日出・日入時刻から航行可能な時間枠を抽出する。"""

    @classmethod
    def get_sun_times(
        cls, umi: "UmiInfo"
    ) -> tuple[datetime.time | None, datetime.time | None]:
        """UmiInfoから正確な日出・日入の time オブジェクトを抽出する。"""
        sunrise_time = None
        sunset_time = None

        if umi.sun_rise and umi.sun_rise != "－－":
            try:
                parts = umi.sun_rise.split(":")
                sunrise_time = datetime.time(int(parts[0]), int(parts[1]))
            except (ValueError, AttributeError, IndexError):
                pass

        if umi.sun_set and umi.sun_set != "－－":
            try:
                parts = umi.sun_set.split(":")
                sunset_time = datetime.time(int(parts[0]), int(parts[1]))
            except (ValueError, AttributeError, IndexError):
                pass

        return sunrise_time, sunset_time
