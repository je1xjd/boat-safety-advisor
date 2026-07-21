"""
marine.py

外部APIおよびスクレイピングによる気象・海象・潮位データの統合取得サービス。
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from engine import (
    AnalysisResult, BoatSafetyEngine, NavigationAnalyzer,
    SafetyRule, TideJudge, UmiInfo, WeatherReport,
    WaveJudge, WindJudge, WindWaveEvaluator
)

from .weather import WeatherAPI
from .scraper import WeatherScraper

logger = logging.getLogger(__name__)


class MarineWeatherClient:
    """外部ソースから海況データを取得・集約するクライアント。"""

    _session = None

    @classmethod
    def get_session(cls) -> requests.Session:
        """シングルトンHTTPセッションを返し、存在しなければ生成する。"""
        if cls._session is None:
            cls._session = cls.create_robust_session()
        return cls._session

    @staticmethod
    def fetch_all_data(date_obj: date) -> tuple[Any, Any, Any]:
        """各データ取得処理を並列実行し、結果をタプルで返す。"""
        date_str = date_obj.strftime("%Y-%m-%d")
        
        with ThreadPoolExecutor(max_workers=3) as pool:
            weather_future = pool.submit(MarineWeatherClient.get_marine_weather, date_str)
            tide_future = pool.submit(MarineWeatherClient.get_tide_data, date_obj)
            umi_info_future = pool.submit(MarineWeatherClient.get_umitenki_tide_info, date_obj)            
            return weather_future.result(), tide_future.result(), umi_info_future.result()

    @staticmethod
    def create_robust_session() -> requests.Session:
        """リトライ機能を備えた高信頼性HTTPセッションを生成する。"""
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

    @staticmethod
    def _fetch_weather_raw(target_date_str: str) -> tuple[dict, dict]:
        """Open-Meteoの天気・海洋APIから生データを並列取得する。"""
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

        # 天気データは必須（例外は呼び出し元でキャッチ）
        w_data = weather_future.result()
        
        # 海洋データは失敗しても警告のみで補完する
        m_data = {}
        try:
            m_data = marine_future.result()
        except Exception as e:
            logger.warning(f"Open-Meteo 沿岸海洋データ取得失敗（欠損扱い）: {e}")

        return w_data, m_data

    @staticmethod
    def _convert_forecast(w_data: dict, m_data: dict) -> WeatherReport:
        """取得した生データを解析し、WeatherReportオブジェクトに変換する。"""
        hourly_data = w_data.get("hourly", {})
        daily_data = w_data.get("daily", {})
    
        raw_winds = hourly_data.get("wind_speed_10m", [None] * 24)
        wind_speed_ms = [(v / 3.6 if v is not None else None) for v in raw_winds]
    
        wind_dirs = hourly_data.get("wind_direction_10m", [None] * 24)
        weather_codes = hourly_data.get("weather_code", [None] * 24)
        times = hourly_data.get("time", [""] * 24)
        precip_probs = hourly_data.get("precipitation_probability", [0] * 24)
    
        daily_weather = daily_data.get("weather_code", [None])[0]
        temp_max = daily_data.get("temperature_2m_max", [0.0])[0]
        temp_min = daily_data.get("temperature_2m_min", [0.0])[0]

        m_hourly = m_data.get("hourly", {})
        wave_heights = m_hourly.get("wave_height", [None] * 24)
        swell_periods = m_hourly.get("swell_wave_period", [None] * 24)

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
    def get_marine_weather(target_date_str: str) -> WeatherReport | None:
        """Open-Meteo APIより大気・海洋データを取得し、構造化されたレポートを返す。"""
        try:
            w_data, m_data = MarineWeatherClient._fetch_weather_raw(target_date_str)
            return MarineWeatherClient._convert_forecast(w_data, m_data)
        except Exception as e:
            logger.error(f"Open-Meteo 大気気象データ解析失敗: {e}")
            return None

    @staticmethod
    def get_tide_data(target_date: date) -> tuple[list, list, list]:
        """気象庁の天文潮位表から毎時潮位と潮汐イベント時刻を抽出する。"""
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
    def get_umitenki_tide_info(target_date: date) -> UmiInfo:
        """海天気.jpから情報を取得し、パースして結果を返す。[cite: 3]"""
        html_text = WeatherAPI.fetch_text(SafetyRule.UMITENKI_BASE_URL)
        return WeatherScraper.parse_umitenki_html(html_text, target_date)
