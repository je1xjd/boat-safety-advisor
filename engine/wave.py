
"""
wave.py

波浪およびうねりの物理的・複合的な安全性判定ロジックを提供する。
"""

from .rules import SafetyRule

class WaveJudge:
    """波浪状況に基づく海域の安全性を評価する。"""

    @staticmethod
    def get_limit_swell(wave_height: float) -> float:
        """波高に応じて動的に変化する制限周期（閾値）を返す。"""
        if wave_height >= SafetyRule.MAX_COMBINED_WAVE_HEIGHT:
            return SafetyRule.MAX_COMBINED_SWELL_PERIOD  # 10.0
        return SafetyRule.MAX_SWELL_PERIOD  # 12.0

    @staticmethod
    def is_physically_safe(wave_height: float, swell_period: float) -> bool:
        """波高と周期が、ボート運航における物理的な限界値を超えていないか判定する。"""
        return (
            wave_height <= SafetyRule.MAX_WAVE_HEIGHT_NORMAL
            and swell_period < SafetyRule.MAX_SWELL_PERIOD
        )

    @staticmethod
    def is_complex_safe(wave_height: float, swell_period: float) -> bool:
        """うねりと波高の相互作用を考慮し、複合的なリスクが許容範囲内か判定する。"""
        # 波高が一定未満なら無条件でセーフ、あるいは「その波高での制限周期未満」であれば安全とする
        return (
            wave_height < SafetyRule.MAX_COMBINED_WAVE_HEIGHT
            or swell_period < WaveJudge.get_limit_swell(wave_height)
        )
