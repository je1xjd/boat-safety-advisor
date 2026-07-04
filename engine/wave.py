from .rules import SafetyRule

class WaveJudge:
    """波やうねりに関する判定ロジックを担当するクラス"""

    @staticmethod
    def is_physically_safe(wave_height: float, swell_period: float) -> bool:
        """物理的限界判定：波高と周期が限界値を超えていないか"""
        return (
            wave_height <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL 
            and swell_period < SafetyRule.MAX_SWELL_PERIOD
        )

    @staticmethod
    def is_complex_safe(wave_height: float, swell_period: float) -> bool:
        """複合危険判定：うねりと波高の組み合わせによる危険性"""
        return not (
            swell_period >= SafetyRule.MAX_COMBINED_SWELL_PERIOD 
            and wave_height >= SafetyRule.MAX_COMBINED_WAVE_HEIGHT
        )

