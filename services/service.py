import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# engine層のモジュール
from engine import (
    AnalysisResult, BoatSafetyEngine, NavigationAnalyzer,
    SafetyRule, TideJudge, UmiInfo, WeatherReport,
    WaveJudge, WindJudge, WindWaveEvaluator
)

from .weather import WeatherAPI
from .scraper import WeatherScraper

# ログ設定
logger = logging.getLogger(__name__)


class MarineWeatherClient:
    """外部APIからデータを取得する責任を持つクラス"""


# 1. セッションを保持する変数を用意
    _session = None

    @classmethod
    def get_session(cls) -> requests.Session:
        """シングルトンセッションを取得する"""
        if cls._session is None:
            cls._session = cls.create_robust_session()
        return cls._session


    @staticmethod
    def fetch_all_data(date_obj: date) -> tuple[Any, Any, Any]:
        """API取得を並列実行して結果をまとめて返す"""
        date_str = date_obj.strftime("%Y-%m-%d")
        
        with ThreadPoolExecutor(max_workers=3) as pool:
            weather_future = pool.submit(MarineWeatherClient.get_marine_weather, date_str)
            tide_future = pool.submit(MarineWeatherClient.get_tide_data, date_obj)
            umi_info_future = pool.submit(MarineWeatherClient.get_umitenki_tide_info, date_obj)            
            return weather_future.result(), tide_future.result(), umi_info_future.result()



# ==============================================================================
# 通信セッション管理
# ==============================================================================
    @staticmethod
    def create_robust_session() -> requests.Session:
        """ネットワーク遅延や一時的な接続切断に対応するため、
        Exponential Backoff 機能を搭載した高信頼性HTTPセッションを生成します。
        """
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoatSafetyClient/3.0"})
    
        retries = Retry(
            total=5,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
    
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    # グローバルセッションの初期化
    # robust_session = create_robust_session()



# ==============================================================================
# 気象・海象・潮汐データ取得
# ==============================================================================
    @staticmethod
    def get_marine_weather(target_date_str: str) -> dict | None:
        """Open-Meteo APIより大気気象および沿岸海洋データを取得し、タイムライン同期を行います。"""
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": SafetyRule.LATITUDE, "longitude": SafetyRule.LONGITUDE,
            "hourly": "wind_speed_10m,wind_direction_10m,weather_code,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "Asia/Tokyo", "start_date": target_date_str, "end_date": target_date_str
        }
    
        marine_url = "https://marine-api.open-meteo.com/v1/marine"
        marine_params = {
            "latitude": SafetyRule.LATITUDE, "longitude": SafetyRule.LONGITUDE,
            "hourly": "wave_height,swell_wave_period",
            "timezone": "Asia/Tokyo", "start_date": target_date_str, "end_date": target_date_str
        }

        def fetch_weather():
            res = MarineWeatherClient.get_session().get(weather_url, params=weather_params, timeout=10)
            res.raise_for_status()
            return res.json()

        def fetch_marine():
            res = MarineWeatherClient.get_session().get(marine_url, params=marine_params, timeout=10)
            res.raise_for_status()
            return res.json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            weather_future = executor.submit(fetch_weather)
            marine_future = executor.submit(fetch_marine)

        try:
            w_data = weather_future.result()
        
            hourly_data = w_data.get("hourly", {})
            daily_data = w_data.get("daily", {})
        
            raw_winds = hourly_data.get("wind_speed_10m", [None] * 24)
            wind_speed_ms = [(v / 3.6 if v is not None else None) for v in raw_winds]
        
            wind_dirs = hourly_data.get("wind_direction_10m", [None] * 24)
            weather_codes = hourly_data.get("weather_code", [None] * 24)
            times = hourly_data.get("time", [""] * 24)
        
            daily_weather = daily_data.get("weather_code", [None])[0]
            temp_max = daily_data.get("temperature_2m_max", [0.0])[0]
            temp_min = daily_data.get("temperature_2m_min", [0.0])[0]
        
        except Exception as e:
            logger.error(f"Open-Meteo 大気気象データ解析失敗: {e}")
            return None

        wave_heights = [None] * 24
        swell_periods = [None] * 24

        try:
            m_data = marine_future.result()
            m_hourly = m_data.get("hourly", {})
            wave_heights = m_hourly.get("wave_height", [None] * 24)
            swell_periods = m_hourly.get("swell_wave_period", [None] * 24)
        except Exception as e:
            logger.warning(f"Open-Meteo 沿岸海洋データ取得失敗（該当項目を欠損として処理継続）: {e}")

        precip_probs = hourly_data.get("precipitation_probability", [0] * 24)

        return WeatherReport(
            times=times,
            wind_speed=wind_speed_ms,
            wind_direction=wind_dirs,
            wave_height=wave_heights,
            swell_period=swell_periods,
            precipitation_probability=precip_probs,
            weather_code=weather_codes,
            daily_weather_code=daily_weather,
            temp_max=temp_max if temp_max is not None else 0.0,
            temp_min=temp_min if temp_min is not None else 0.0,
        )


    @staticmethod
    def get_tide_data(target_date: datetime.date) -> tuple[list, list, list]:
        """気象庁提供の天文潮位表から毎時潮位と動的イベント時刻を抽出します。"""
        tide_list = [None] * 24
        year_str = target_date.strftime("%Y")
        url = f"{SafetyRule.JMA_TIDE_BASE_URL}/{year_str}/{SafetyRule.TIDE_STATION_CODE}.txt"

        try:
            response = MarineWeatherClient.get_session().get(url, timeout=10)
            response.raise_for_status()
            lines = response.text.splitlines()
            target_token = target_date.strftime("%y") + f"{target_date.month:2}" + f"{target_date.day:2}"

            for line in lines:
                if len(line) < 80: continue
                if line[72:78] == target_token and line[78:80].strip() == SafetyRule.TIDE_STATION_CODE:
                    temp_tides = []
                    for h_idx in range(24):
                        start = h_idx * 3
                        val_str = line[start:start+3].strip()
                        temp_tides.append(None if (val_str == "999" or not val_str) else float(val_str))
                
                    if len(temp_tides) == 24: tide_list = temp_tides

                    high_tide_minutes = []
                    low_tide_minutes = []
                    for i in range(4):
                        p_high = 80 + (i * 7)
                        r_high = line[p_high:p_high+4]
                        if r_high.strip() and "9999" not in r_high:
                            high_tide_minutes.append(int(r_high.replace(" ", "0")[:2]) * 60 + int(r_high.replace(" ", "0")[2:]))
                    
                        p_low = 108 + (i * 7)
                        r_low = line[p_low:p_low+4]
                        if r_low.strip() and "9999" not in r_low:
                            low_tide_minutes.append(int(r_low.replace(" ", "0")[:2]) * 60 + int(r_low.replace(" ", "0")[2:]))

                    return tide_list, high_tide_minutes, low_tide_minutes
        except Exception as e:
            logger.error(f"気象庁天文潮位データパース例外発生: {e}")

        return tide_list, [], []


    @staticmethod
    def get_umitenki_tide_info(target_date: datetime.date) -> UmiInfo:
        """通信担当と解析担当を連携させ、海天気.jpから情報を取得します。"""
        # 1. 通信担当(WeatherAPI)からHTMLをもらう
        html_text = WeatherAPI.fetch_text(SafetyRule.UMITENKI_BASE_URL)
        
        # 2. 解析担当(WeatherScraper)にHTMLを渡して結果をもらう
        return WeatherScraper.parse_umitenki_html(html_text, target_date)


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
