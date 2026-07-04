from .rules import SafetyRule
from .wind import WindJudge 
from .wave import WaveJudge

class WindWaveEvaluator:
    """風と波の判定ロジックを専門に扱うクラス"""

    @staticmethod
    def judge(hour: int, wind_speed: float | None, wind_dir: float | None,
              wave_height: float | None, swell_period: float | None,
              is_ebb: bool) -> bool:
        """風・波・運用条件に基づき総合判定する。"""

        # 入力チェック
        if any(v is None for v in [wind_speed, wind_dir, wave_height, swell_period]):
            return False

        # 物理判定
        if not WaveJudge.is_physically_safe(wave_height, swell_period):
            return False
        if not WaveJudge.is_complex_safe(wave_height, swell_period):
            return False

        # 運用判定
        is_south = WindJudge.is_south_wind(wind_dir)
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        
        limit = WindJudge.get_limit(is_ebb, is_south, wave_height <= limit_wave)
        
        return WindJudge.is_safe(wind_speed, limit, wave_height)


