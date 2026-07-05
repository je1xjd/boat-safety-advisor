from datetime import datetime

from engine import (
    AnalysisResult,
    NavigationAnalyzer,
)

from .marine import MarineWeatherClient

class BoatDataService:
    @staticmethod
    def get_full_analysis(target_date) -> AnalysisResult:
        """日付を受け取り、データ取得から分析までを一括で行う"""
        date_obj = target_date if not isinstance(target_date, str) else datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # 1. データ取得
        weather, tide, umi = MarineWeatherClient.fetch_all_data(date_obj)

        # 2. 分析結果生成（整理されたメソッドを呼び出す）
        return BoatDataService.build_analysis_data(weather, tide, umi)

    @staticmethod
    def build_analysis_data(weather_info, tide_data, umi_info) -> AnalysisResult:
        """取得済みデータを分析し、結果オブジェクトを返す"""
        if not weather_info or not tide_data:
            return None

        tide_result, high_tides, low_tides = tide_data
        
        # 1. HourForecastリスト生成
        hour_data = NavigationAnalyzer.build_hour_data(
            weather_info, tide_result, high_tides, low_tides
        )
        
        # 2. AnalysisSummaryオブジェクト生成
        summary = NavigationAnalyzer.build_navigation_summary(hour_data)
        
        # 3. まとめ
        return AnalysisResult(
            hour_data=hour_data,
            summary=summary,
            weather_info=weather_info,
            umi_info=umi_info
        )

