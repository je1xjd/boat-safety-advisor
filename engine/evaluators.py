from .rules import SafetyRule
from .wind import WindJudge 
from .wave import WaveJudge

class WindWaveEvaluator:
    """風と波の判定ロジックを専門に扱うクラス"""

    @staticmethod
    def judge(hour: int, wind_speed: float | None, wind_dir: float | None,
              wave_height: float | None, swell_period: float | None,
              is_ebb: bool) -> bool: 

        if wind_speed is None or wind_dir is None or wave_height is None or swell_period is None:
            return False

        # 1. 波・うねりの物理判定
        if not WaveJudge.is_physically_safe(wave_height, swell_period):
            return False

        # 2. 複合危険判定
        if not WaveJudge.is_complex_safe(wave_height, swell_period):
            return False

        # 3. 運用制約・風速判定
        is_south = WindJudge.is_south_wind(wind_dir)
        
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        is_under_operational_limit = wave_height <= limit_wave

        limit = WindJudge.get_limit(is_ebb, is_south, is_under_operational_limit)
        
        return WindJudge.is_safe(wind_speed, limit, wave_height)


