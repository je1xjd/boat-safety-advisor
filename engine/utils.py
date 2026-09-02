"""
utils.py

UI表示用の気象要約および時間計算ユーティリティ。
"""

import datetime

WEATHER_MAPPING = {
    0: {"emoji": "☀️", "name": "晴れ"},
    1: {"emoji": "🌤️", "name": "晴れ時々曇り"},
    2: {"emoji": "⛅", "name": "曇り時々晴れ"},
    3: {"emoji": "☁️", "name": "曇り"},
    45: {"emoji": "🌫️", "name": "霧"},
    48: {"emoji": "🌫️", "name": "霧氷"},
    51: {"emoji": "☂️", "name": "小雨（霧雨）"},
    53: {"emoji": "☂️", "name": "雨（霧雨）"},
    55: {"emoji": "☔", "name": "強い霧雨"},
    56: {"emoji": "☂️", "name": "凍結性霧雨"},
    57: {"emoji": "☔", "name": "強い凍結性霧雨"},
    61: {"emoji": "☂️", "name": "小雨"},
    63: {"emoji": "☂️", "name": "雨"},
    65: {"emoji": "☔", "name": "大雨"},
    66: {"emoji": "☂️", "name": "凍結性の雨"},
    67: {"emoji": "☔", "name": "強い凍結性の雨"},
    71: {"emoji": "🌨️", "name": "小雪"},
    73: {"emoji": "⛄", "name": "雪"},
    75: {"emoji": "⛄", "name": "大雪"},
    77: {"emoji": "🌨️", "name": "霧雪"},
    80: {"emoji": "☂️", "name": "にわか雨"},
    81: {"emoji": "☂️", "name": "雨（にわか雨）"},
    82: {"emoji": "☔", "name": "激しいにわか雨"},
    85: {"emoji": "🌨️", "name": "にわか雪"},
    86: {"emoji": "⛄", "name": "強いにわか雪"},
    95: {"emoji": "⚡", "name": "雷雨"},
    96: {"emoji": "⚡", "name": "雷雨（ひょう伴う）"},
    99: {"emoji": "⚡", "name": "激しい雷雨（ひょう伴う）"},
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
            return 3
        
        severe_codes = [95, 65, 55, 63, 61, 53, 51, 80, 75, 73, 71, 85]
        for severe in severe_codes:
            if severe in codes:
                return severe
                
        return max(codes)

    morning_codes = weather_codes[7:13]
    afternoon_codes = weather_codes[13:19]

    morning_main = get_worst_weather_code(morning_codes)
    afternoon_main = get_worst_weather_code(afternoon_codes)

    m_info = WEATHER_MAPPING.get(morning_main, {"emoji": "☁️", "name": "曇り"})
    a_info = WEATHER_MAPPING.get(afternoon_main, {"emoji": "☁️", "name": "曇り"})

    if morning_main == afternoon_main or m_info["name"] == a_info["name"]:
        weather_str = f"{m_info['emoji']} {m_info['name']}"
    else:
         weather_str = f"{m_info['emoji']}/{a_info['emoji']} {m_info['name']}／{a_info['name']}"

    morning_precip = get_period_precip(*MORNING_RANGE)
    afternoon_precip = get_period_precip(*AFTERNOON_RANGE)

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
