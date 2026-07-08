"""
analysis.py

気象・潮汐データの取得から航行分析結果の生成までを統括するサービスレイヤー。
"""

import datetime
from engine import AnalysisResult, NavigationAnalyzer
from .marine import MarineWeatherClient

class BoatDataService:
    """外部サービスからのデータ取得と分析処理を仲介するサービス。"""

    @staticmethod
    def get_full_analysis(target_date: str | datetime.date) -> AnalysisResult:
        """指定された日付のデータを取得し、一括で分析結果を生成する。"""
        # datetimeモジュール内のdatetimeクラスを使用
        date_obj = (
            target_date 
            if not isinstance(target_date, str) 
            else datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        )
        
        weather, tide, umi = MarineWeatherClient.fetch_all_data(date_obj)
        return BoatDataService.build_analysis_data(weather, tide, umi)

    @staticmethod
    def build_analysis_data(weather_info, tide_data, umi_info) -> AnalysisResult | None:
        """取得した生データを解析し、分析結果オブジェクトを構築する。"""
        if not weather_info or not tide_data:
            return None

        tide_result, high_tides, low_tides = tide_data
        
        hour_data = NavigationAnalyzer.build_hour_data(
            weather_info, tide_result, high_tides, low_tides
        )
        
        summary = NavigationAnalyzer.build_navigation_summary(hour_data)
        
        return AnalysisResult(
            hour_data=hour_data,
            summary=summary,
            weather_info=weather_info,
            umi_info=umi_info
        )
