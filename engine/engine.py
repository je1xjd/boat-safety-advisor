from .models import UmiInfo, HourForecast, AnalysisResult, AnalysisSummary
from .rules import SafetyRule
from .tide import TideJudge
from .evaluators import WindWaveEvaluator
from .wave import WaveJudge

class BoatSafetyEngine:
    """相模川河口海域における固有の気象・海象リスクを多角的に評価する判定エンジン。"""
    
    @classmethod
    def judge_wind_wave_only(
        cls, hour: int, wind_speed: float | None, wind_dir: float | None,
        wave_height: float | None, swell_period: float | None,
        high_tides: list[int], low_tides: list[int]
    ) -> bool:

        """風速・風向・沿岸波浪・長周期うねり等の気象海象条件を基準値に基づき単独判定します。"""
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
        is_ebb = TideJudge.is_ebbing_tide(hour, high_tides, low_tides)
        
        limit_wave = SafetyRule.MAX_WAVE_HEIGHT_STRICT if (is_south or is_ebb) else SafetyRule.MAX_WAVE_HEIGHT_NORMAL
        is_under_operational_limit = wave_height <= limit_wave

        limit = WindJudge.get_limit(is_ebb, is_south, is_under_operational_limit)
        
        return WindJudge.is_safe(wind_speed, limit, wave_height)


    @classmethod
    def judge_safety(cls, hour, wind_speed, wind_dir, wave_height, swell_period, tide_val, high_tides, low_tides) -> bool:
        # 1. 司令塔として計算
        is_ebb = TideJudge.is_ebbing_tide(hour, high_tides, low_tides)
        
        # 2. 結果を計算機に渡す
        wind_wave_ok = WindWaveEvaluator.judge(
            hour, wind_speed, wind_dir, wave_height, swell_period, is_ebb
        )
        
        # 3. 統合判定（TideJudgeもここで利用）
        tide_safe = TideJudge.is_tide_safe(tide_val)
        
        return wind_wave_ok and tide_safe

    @classmethod
    def calculate_valid_windows(cls, hour_data: dict) -> tuple[list, list, list]:

        status_map = {}

        for hour in range(
            SafetyRule.ACTIVITY_START_HOUR,
            SafetyRule.ACTIVITY_END_HOUR
        ):

            if hour not in hour_data:
                continue

            data = hour_data[hour]

            # 辞書アクセスを属性アクセスに変更
            if data.is_safe:

                status_map[hour] = "safe"

            elif (
                data.wind_wave_safe
                and data.tide is not None
                and data.tide < SafetyRule.MIN_TIDE_CM
            ):

                status_map[hour] = "tide_low"

            else:

                status_map[hour] = "danger"

        status_map = cls.normalize_status_sequence(
            status_map
        )

        valid_windows = []

        for start_hour in range(
            SafetyRule.ACTIVITY_START_HOUR,
            SafetyRule.ACTIVITY_END_HOUR
        ):
            for end_hour in range(start_hour + SafetyRule.REQUIRED_SAFE_HOURS - 1, SafetyRule.ACTIVITY_END_HOUR):
                all_safe = True
                for h in range(start_hour, end_hour + 1):

                    if h not in status_map:
                        all_safe = False
                        break

                    if status_map[h] == "danger":
                        all_safe = False
                        break
                if all_safe:
                    duration = end_hour - start_hour + 1
                    valid_windows.append((start_hour, end_hour + 1, duration))

        low_hours = [
            h
            for h, status in status_map.items()
            if status == "tide_low"
        ]

        if low_hours:

            first_low = min(low_hours)
            last_low = max(low_hours)

            before_candidates = [
                w for w in valid_windows
                if w[1] <= first_low
            ]

            after_candidates = [
                w for w in valid_windows
                if w[0] > last_low
            ]
        else:
            before_candidates = valid_windows
            after_candidates = []

        return valid_windows, before_candidates, after_candidates



    @classmethod
    def _normalize_tide_sequence(cls, status_map: dict) -> dict:
        """
        仕様: 
        前後が両方 "safe" の場合にのみ "tide_low" を維持。
        それ以外（片方でも danger や夜間など）は "danger" に格下げ。
        """
        normalized = status_map.copy()
        hours = sorted(status_map.keys())

        for i, hour in enumerate(hours):
            if status_map[hour] != "tide_low":
                continue

            start = i
            while i + 1 < len(hours) and status_map[hours[i + 1]] == "tide_low":
                i += 1
            end = i

            # 前後の状態を取得（存在しない場合は危険とみなす）
            prev_status = status_map.get(hours[start - 1], "danger") if start > 0 else "danger"
            next_status = status_map.get(hours[end + 1], "danger") if end < len(hours) - 1 else "danger"

            # 前後両方が safe でなければ danger に置換
            if not (prev_status == "safe" and next_status == "safe"):
                for j in range(start, end + 1):
                    normalized[hours[j]] = "danger"
        
        return normalized

    @classmethod
    def get_display_status(cls, hour: int, data: object, sunrise_hour: int, sunset_hour: int) -> tuple[str, str]:
        """
        時間外・安全性・潮位判定を一元管理する。
        戻り値: (表示ラベル, タグ)
        """
        # 1. 時間外判定 (最優先)
        if not (sunrise_hour <= hour < sunset_hour):
            label = "日没" if hour >= sunset_hour else "夜明"
            return label, "danger"

        # 2. 安全判定
        if data.is_safe:
            return "○ 安全", "safe"
        
        # 3. 潮位判定
        if getattr(data, 'is_tide_warning', False):
            return "△ 潮位", "tide_low"
            
        # 4. その他（物理的危険・座礁リスク）
        return "× 危険", "danger"


    @classmethod
    def normalize_status_sequence(
        cls,
        status_map: dict
    ) -> dict:

        hours = sorted(status_map.keys())

        # --------------------------------------------------
        # 潮位低下区間を抽出
        # --------------------------------------------------

        i = 0

        while i < len(hours):

            hour = hours[i]

            if status_map[hour] != "tide_low":
                i += 1
                continue

            start = i

            while (
                i + 1 < len(hours)
                and status_map[hours[i + 1]] == "tide_low"
            ):
                i += 1

            end = i

            before_safe = False
            after_safe = False

            if start > 0:
                before_safe = (
                    status_map[hours[start - 1]]
                    == "safe"
                )

            if end < len(hours) - 1:
                after_safe = (
                    status_map[hours[end + 1]]
                    == "safe"
                )

            # --------------------------------------------------
            # 前後とも安全でない潮位低下区間は危険へ変更
            # --------------------------------------------------

            if not (before_safe and after_safe):

                for j in range(start, end + 1):
                    status_map[hours[j]] = "danger"

            i += 1

        return status_map








    @classmethod
    def build_before_after_summary(
        cls,
        before_candidates: list,
        after_candidates: list
    ) -> tuple[str, str]:

        before_str = "該当なし"

        if before_candidates:
            best_b = max(before_candidates, key=lambda x: x[2])
            before_str = f"{best_b[0]:02d}-{best_b[1]:02d}時"

        after_str = "該当なし"

        if after_candidates:
            best_a = max(after_candidates, key=lambda x: x[2])
            after_str = f"{best_a[0]:02d}-{best_a[1]:02d}時"

        return before_str, after_str

    @classmethod
    def get_best_window(
        cls,
        valid_windows: list
    ) -> tuple:

        if not valid_windows:
            return (0, 0, 0)

        return max(valid_windows, key=lambda x: x[2])








    @staticmethod
    def get_ui_tide_text(umi: UmiInfo) -> str:
        return (f"🌀 {umi.tide_name} "
                f"(満潮 {umi.high_tide} ／ 干潮 {umi.low_tide})   "
                f"🌗 月齢: {umi.moon_age}   "
                f"🌅 日出: {umi.sun_rise} ／ 日入: {umi.sun_set}")



    @classmethod
    def judge_sea_condition_pure(
        cls, wind_speed: float, wave_height: float, swell_period: float
    ) -> bool:
        """潮位や風向などの運用条件を排除した、純粋な物理的限界のみによる海況判定"""
        # 通常の安全基準のみを使用
        if wave_height > SafetyRule.MAX_WAVE_HEIGHT_NORMAL:
            return False
        if swell_period >= SafetyRule.MAX_SWELL_PERIOD:
            return False
        if wind_speed > SafetyRule.WIND_LIMIT_NORMAL:
            return False
        return True


    @classmethod
    def apply_sequence_rules(cls, hour_data: dict, sunrise_hour: int, sunset_hour: int):
        hours = sorted(hour_data.keys())
        
        # 1. 物理的な「絶対安全/危険」をまず確定させる
        # (潮位はここでは考慮せず、風・波・時間外のみで判定)
        for hour in hours:
            data = hour_data[hour]
            is_time_ok = (sunrise_hour <= hour < sunset_hour)
            # 物理的に安全な時間帯のみTrue
            data.is_safe = is_time_ok and data.wind_wave_safe
            data.is_tide_warning = False

        # 2. 潮位低下の連続期間（ブロック）を特定して判定する
        # 潮位低下が続く期間を抽出し、その前後が安全かを確認する
        i = 0
        while i < len(hours):
            if hour_data[hours[i]].is_tide_low():
                # 潮位低下期間の開始と終了を探す
                start = i
                while i < len(hours) and hour_data[hours[i]].is_tide_low():
                    i += 1
                end = i - 1
                
                # ブロックの前後が安全かチェック
                prev_h = hours[start - 1] if start > 0 else None
                next_h = hours[end + 1] if end < len(hours) - 1 else None
                
                prev_safe = (prev_h is not None and hour_data[prev_h].is_safe)
                next_safe = (next_h is not None and hour_data[next_h].is_safe)
                
                # ブロック全体を潮位注意にするか、それとも危険にするか
                if prev_safe and next_safe:
                    for idx in range(start, end + 1):
                        hour_data[hours[idx]].is_tide_warning = True
                        hour_data[hours[idx]].is_safe = False # 黄色にするため
                else:
                    # 前後が安全でない場合、この期間は座礁リスクのため「危険」のまま
                    for idx in range(start, end + 1):
                        hour_data[hours[idx]].is_safe = False
            else:
                i += 1


    @classmethod
    def get_status_strict(cls, hour_data: HourForecast, tide_cm: float | None) -> str:
        """
        [STEP 1 追加] 判定専用メソッド
        物理条件・潮位のみでステータスを判定します（ラベルや前後チェックは行わない）
        """
        if not hour_data.wind_wave_safe:
            return "danger"
        if tide_cm is not None and tide_cm < SafetyRule.MIN_TIDE_CM:
            return "tide_low"
        return "safe"

    @classmethod
    def normalize_status_sequence_standalone(cls, status_map: dict) -> dict:
        """
        [STEP 1 追加] 正規化専用メソッド
        前後関係のルールを適用します
        """
        hours = sorted(status_map.keys())
        new_map = status_map.copy()
        for i, hour in enumerate(hours):
            if new_map[hour] != "tide_low": continue
            start = i
            while i + 1 < len(hours) and new_map[hours[i + 1]] == "tide_low": i += 1
            end = i
            prev = new_map.get(hours[start - 1]) if start > 0 else "danger"
            next = new_map.get(hours[end + 1]) if end < len(hours) - 1 else "danger"
            
            # 前後が両方 safe でなければ danger に置換
            if not (prev == "safe" and next == "safe"):
                for j in range(start, end + 1): new_map[hours[j]] = "danger"
        return new_map
