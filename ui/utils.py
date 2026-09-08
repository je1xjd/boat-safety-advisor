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


def get_wind_arrow(direction_input, use_emoji: bool = True) -> str:
    """
    風向の文字列、または角度（数値）を8〜16方向の進行方向矢印に変換する共通関数（風の抜ける向き）
    :param direction_input: 風向の文字列または数値（角度）
    :param use_emoji: Trueならカラー絵文字（Web版向け）、Falseなら制御文字を含まないプレーンな矢印（デスクトップ版向け）
    """
    # 数値（角度）で渡された場合は、16方位の文字列に変換する
    try:
        deg = float(direction_input) % 360
        directions_16 = [
            "北", "北北東", "北東", "東北東",
            "東", "東南東", "南東", "南南東",
            "南", "南南西", "南西", "西南西",
            "西", "西北西", "北西", "北北西"
        ]
        idx = int((deg + 11.25) // 22.5) % 16
        d = directions_16[idx]
    except (ValueError, TypeError):
        d = str(direction_input)
    
    # 複合方位（北西、北東、南東、南西系）の判定
    if "北北西" in d or "西北西" in d or "北西" in d:
        arrow = "↘️"
    elif "北北東" in d or "東北東" in d or "北東" in d:
        arrow = "↙️"
    elif "南南東" in d or "東南東" in d or "南東" in d:
        arrow = "↖️"
    elif "南南西" in d or "西南西" in d or "南西" in d:
        arrow = "↗️"
    # 基本の4方位
    elif "北" in d:
        arrow = "⬇️"
    elif "南" in d:
        arrow = "⬆️"
    elif "東" in d:
        arrow = "⬅️"
    elif "西" in d:
        arrow = "➡️"
    else:
        arrow = "・"
    
    # デスクトップ版などでプレーンなテキスト記号にしたい場合は、異体字セレクタ（\ufe0f）を除去する
    if not use_emoji:
        arrow = arrow.replace("\ufe0f", "")
        
    return arrow
