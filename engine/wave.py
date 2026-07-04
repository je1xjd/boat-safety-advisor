from .rules import SafetyRule

class WaveJudge:
    """波やうねりに関する判定を担当するクラス"""

    @staticmethod
    def is_physically_safe(wave_height: float, swell_period: float) -> bool:
        """物理的限界（波高・周期）による安全判定"""
        return (
            wave_height <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL and
            swell_period < SafetyRule.MAX_SWELL_PERIOD
        )

    @staticmethod
    def is_complex_safe(wave_height: float, swell_period: float) -> bool:
        """複合要因（うねりと波高の組み合わせ）による安全判定"""
        return (
            swell_period < SafetyRule.MAX_COMBINED_SWELL_PERIOD or
            wave_height < SafetyRule.MAX_COMBINED_WAVE_HEIGHT
        )
