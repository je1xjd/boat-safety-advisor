"""
tide.py

潮汐・潮位の評価ロジックを提供する。
"""

from .rules import SafetyRule

class TideJudge:
    """潮汐の状態および潮位の安全性判定を行う。"""

    @staticmethod
    def is_ebbing_tide(current_hour: int, high_tides: list[int], low_tides: list[int]) -> bool:
        """指定された時間帯が、潮位が下降している「下げ潮（落潮）」の状態か判定する。"""
        if not high_tides and not low_tides:
            return False
            
        current_minutes = current_hour * 60 + 30
        all_events = [(t, "high") for t in high_tides] + [(t, "low") for t in low_tides]
        all_events.sort(key=lambda x: x[0])
        
        last_event_type = None

        for event_time, event_type in all_events:
            if event_time > current_minutes:
                break
            last_event_type = event_type
            
        if last_event_type is None:
            last_event_type = "low" if all_events[0][1] == "high" else "high"
            
        return last_event_type == "high"

    @staticmethod
    def is_tide_safe(tide_cm: float | None) -> bool:
        """潮位が航行に必要な最低基準値を満たしているか判定する。"""
        return tide_cm is not None and tide_cm >= SafetyRule.MIN_TIDE_CM

    @staticmethod
    def is_tide_low(tide_cm: float | None) -> bool:
        """潮位が座礁リスクを伴う危険な水準にあるか判定する。"""
        if tide_cm is None:
            return False
        return tide_cm < SafetyRule.MIN_TIDE_CM
