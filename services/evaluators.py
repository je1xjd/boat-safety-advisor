"""
evaluators.py

気象・海象データの評価ロジックを提供する。
"""

from .rules import SafetyRule
from .wind import WindJudge 
from .wave import WaveJudge

class WindWaveEvaluator:
    """風と波に関する総合的な安全判定を行う。"""

    @staticmethod
    def judge(hour: int, wind_speed: float | None, wind_dir: float | None,
              wave_height: float | None, swell_period: float | None,
              is_ebb: bool) -> bool:
        """風速、風向、波高、うねり、および潮汐条件に基づき安全性を判定する。"""


        if any(v is None for v in [wind_speed, wind_dir, wave_height, swell_period]):
            return False

        if not WaveJudge.is_physically_safe(wave_height, swell_period):
            return False
        if not WaveJudge.is_complex_safe(wave_height, swell_period):
            return False

        is_south = WindJudge.is_south_wind(wind_dir)
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        
        limit = WindJudge.get_limit(is_ebb, is_south, wave_height <= limit_wave)
        
        return WindJudge.is_safe(wind_speed, limit, wave_height)
