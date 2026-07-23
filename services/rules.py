"""
rules.py

海況判定に関する各種基準値を管理する。
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class SafetyRule:
    """海況判定の基準値を一元管理する定数クラス。"""

    LATITUDE: float = 35.316
    LONGITUDE: float = 139.370

    MIN_TIDE_CM: float = 70.0

    MAX_WAVE_HEIGHT_NORMAL: float = 1.0
    MAX_WAVE_HEIGHT_STRICT: float = 0.8
    MAX_SWELL_PERIOD: float = 12.0
    MAX_COMBINED_SWELL_PERIOD: float = 10.0
    MAX_COMBINED_WAVE_HEIGHT: float = 0.7

    SOUTH_WIND_START: float = 157.5
    SOUTH_WIND_END: float = 202.5
    DIR_EAST_SOUTH: float = 112.5
    DIR_SOUTH_WEST: float = 247.5

    ACTIVITY_START_HOUR: int = 7
    ACTIVITY_END_HOUR: int = 18
    FETCH_END_HOUR: int = 19
    REQUIRED_SAFE_HOURS: int = 3

    WIND_LIMIT_CRITICAL: float = 5.5
    WIND_LIMIT_EBB: float = 7.0
    WIND_LIMIT_SOUTH: float = 7.5
    WIND_LIMIT_NORMAL: float = 9.0
    WIND_OVERRIDE_MARGIN: float = 1.0
    WIND_OVERRIDE_WAVE_HEIGHT: float = 0.4

    WIND_Y_LIMIT = 15
    WAVE_Y_LIMIT = 3
    TIDE_Y_LIMIT = 200

    WIND_COLOR: str = "#1f77b4"
    WAVE_COLOR: str = "#3b5998"
    TIDE_COLOR: str = "#2ca02c"


    TIDE_STATION_CODE: str = "D8"
    JMA_TIDE_BASE_URL: str = "https://www.data.jma.go.jp/kaiyou/data/db/tide/suisan/txt"
    UMITENKI_BASE_URL: str = "https://www.umitenki.jp/tenki/1545/14days"
