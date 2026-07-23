"""
wave.py

波浪およびうねりの物理的・複合的な安全性判定ロジックを提供する。
"""

from .rules import SafetyRule

class WaveJudge:
    """波浪状況に基づく海域の安全性を評価する。"""

    @staticmethod
    def is_physically_safe(wave_height: float, swell_period: float) -> bool:
        """波高と周期が、ボート運航における物理的な限界値を超えていないか判定する。"""
        return (
            wave_height <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL and
            swell_period < SafetyRule.MAX_SWELL_PERIOD
        )

    @staticmethod
    def is_complex_safe(wave_height: float, swell_period: float) -> bool:
        """うねりと波高の相互作用を考慮し、複合的なリスクが許容範囲内か判定する。"""
        return (
            swell_period < SafetyRule.MAX_COMBINED_SWELL_PERIOD or
            wave_height < SafetyRule.MAX_COMBINED_WAVE_HEIGHT
        )
