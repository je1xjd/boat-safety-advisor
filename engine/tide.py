from .rules import SafetyRule

class TideJudge:
    """潮汐・潮位に関する判定ロジックを担当するクラス"""

    @staticmethod
    def is_ebbing_tide(current_hour: int, high_tides: list[int], low_tides: list[int]) -> bool:
        """潮汐イベント時刻より、指定された時間帯が「下げ潮（落潮）」状態にあるかを厳密に判定します。"""
        if not high_tides and not low_tides:
            return False
            
        current_minutes = current_hour * 60 + 30  # 該当時間帯の中央値（30分時点）で評価
        all_events = [(t, "high") for t in high_tides] + [(t, "low") for t in low_tides]
        all_events.sort(key=lambda x: x[0])
        
        last_event_type = None
        for event_time, event_type in all_events:
            if event_time <= current_minutes:
                last_event_type = event_type
            else:
                break
                
        if last_event_type is None:
            last_event_type = "low" if all_events[0][1] == "high" else "high"
            
        return last_event_type == "high"

    @staticmethod
    def is_tide_safe(tide_cm: float | None) -> bool:
        """潮位が安全基準を満たしているか"""
        if tide_cm is None:
            return False
        return tide_cm >= SafetyRule.MIN_TIDE_CM

    @staticmethod
    def is_tide_low(tide_cm: float | None) -> bool:
        """潮位が基準を下回っている（注意が必要な）状態か"""
        if tide_cm is None:
            return False
        return tide_cm < SafetyRule.MIN_TIDE_CM
