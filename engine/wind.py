from .rules import SafetyRule

class WindJudge:
    """風に関する判定を担当するクラス"""

    @staticmethod
    def degrees_to_direction(deg: float) -> str:
        """風向（度）を16方位の文字列に変換する"""
        directions = [
            "北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
            "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"
        ]
        return directions[int((deg + 11.25) / 22.5) % 16]

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
        # 風速が上限以下の場合は安全
        if wind_speed <= limit:
            return True

        # 上限を超えていても例外許可条件を満たせば安全
        if (
            wind_speed <= limit + SafetyRule.WIND_OVERRIDE_MARGIN and
            wave_height < SafetyRule.WIND_OVERRIDE_WAVE_HEIGHT
        ):
            return True

        return False
