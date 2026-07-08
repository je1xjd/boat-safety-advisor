"""
wind.py

風速・風向に基づく航行の安全判定および風向の変換を行う。
"""

from .rules import SafetyRule

class WindJudge:
    """風に関する安全判定ロジックを提供する。"""

    @staticmethod
    def degrees_to_direction(deg: float) -> str:
        """風向（度）を16方位の文字列に変換する。"""
        directions = [
            "北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
            "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"
        ]
        return directions[int((deg + 11.25) / 22.5) % 16]

    @staticmethod
    def is_south_wind(wind_dir: float) -> bool:
        """南風（運航リスクが高まる風向）の範囲内か判定する。"""
        return SafetyRule.SOUTH_WIND_START <= wind_dir <= SafetyRule.SOUTH_WIND_END

    @staticmethod
    def get_limit(is_ebb: bool, is_south: bool, is_under_operational_limit: bool) -> float:
        """潮流と風向の状況を組み合わせ、運航可能な風速上限値を算出する。"""
        if is_ebb and is_south:
            return SafetyRule.WIND_LIMIT_CRITICAL
        if is_ebb or is_south or not is_under_operational_limit:
            return SafetyRule.WIND_LIMIT_EBB
        return SafetyRule.WIND_LIMIT_NORMAL

    @staticmethod
    def is_safe(wind_speed: float, limit: float, wave_height: float) -> bool:
        """風速が上限以下か、または波高による補完基準（マージン）を考慮して判定する。"""
        if wind_speed <= limit:
            return True

        return (
            wind_speed <= limit + SafetyRule.WIND_OVERRIDE_MARGIN and
            wave_height < SafetyRule.WIND_OVERRIDE_WAVE_HEIGHT
        )
