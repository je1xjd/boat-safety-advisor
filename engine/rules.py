from dataclasses import dataclass

@dataclass(frozen=True)
class SafetyRule:
    """海況判定の基準値を管理する設定クラス"""
    
    # 地理座標
    LATITUDE: float = 35.316
    LONGITUDE: float = 139.370

    # 潮位制限
    MIN_TIDE_CM: float = 70.0

    # 波浪制限
    MAX_WAVE_HEIGHT_NORMAL: float = 1.0
    MAX_WAVE_HEIGHT_STRICT: float = 0.8

    # うねり制限
    MAX_SWELL_PERIOD: float = 12.0
    MAX_COMBINED_SWELL_PERIOD: float = 10.0
    MAX_COMBINED_WAVE_HEIGHT: float = 0.7

    # 風向判定範囲
    SOUTH_WIND_START: float = 157.5
    SOUTH_WIND_END: float = 202.5
    DIR_EAST_SOUTH: float = 112.5
    DIR_SOUTH_WEST: float = 247.5

    # 運航時間枠
    ACTIVITY_START_HOUR: int = 7
    ACTIVITY_END_HOUR: int = 18
    REQUIRED_SAFE_HOURS: int = 3

    # 風速制限 (m/秒)
    WIND_LIMIT_CRITICAL: float = 5.5
    WIND_LIMIT_EBB: float = 7.0
    WIND_LIMIT_SOUTH: float = 7.5
    WIND_LIMIT_NORMAL: float = 9.0

    # 風速超過時の例外許可条件
    WIND_OVERRIDE_MARGIN: float = 1.0
    WIND_OVERRIDE_WAVE_HEIGHT: float = 0.4

    # 外部データソース参照先
    TIDE_STATION_CODE: str = "D8"
    JMA_TIDE_BASE_URL: str = "https://www.data.jma.go.jp/kaiyou/data/db/tide/suisan/txt"
    UMITENKI_BASE_URL: str = "https://www.umitenki.jp/tenki/1545/14days"
