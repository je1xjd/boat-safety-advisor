"""
marine.py

外部APIおよび天文計算による気象・海象・潮位データの統合取得サービス。
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from engine import (
    SafetyRule,
    UmiInfo,
    WeatherReport,
)

logger = logging.getLogger(__name__)


class MarineWeatherClient:
    """
    外部ソースから海況データを取得・集約するクライアント。
    """

    _session = None

    @classmethod
    def get_session(cls) -> requests.Session:
        """シングルトンHTTPセッションを返す。"""
        if cls._session is None:
            cls._session = cls.create_robust_session()
        return cls._session

    @staticmethod
    def fetch_all_data(date_obj: date) -> tuple[Any, Any, Any]:
        """各データ取得処理を並列実行し、結果をタプルで返す。"""
        date_str = date_obj.strftime("%Y-%m-%d")

        with ThreadPoolExecutor(max_workers=3) as pool:
            weather_future = pool.submit(
                MarineWeatherClient.get_marine_weather, date_str
            )
            tide_future = pool.submit(MarineWeatherClient.get_tide_data, date_obj)
            umi_info_future = pool.submit(
                MarineWeatherClient.get_moon_age_info, date_obj
            )
            return (
                weather_future.result(),
                tide_future.result(),
                umi_info_future.result(),
            )

    @staticmethod
    def create_robust_session() -> requests.Session:
        """リトライ機能を備えた高信頼性HTTPセッションを生成する。"""
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
        )

        retries = Retry(
            total=5,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @staticmethod
    def _fetch_weather_raw(target_date_str: str) -> tuple[dict, dict]:
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": SafetyRule.LATITUDE,
            "longitude": SafetyRule.LONGITUDE,
            "hourly": "wind_speed_10m,wind_direction_10m,weather_code,precipitation_probability,temperature_2m",
            "daily": "weather_code",
            "timezone": "Asia/Tokyo",
            "start_date": target_date_str,
            "end_date": target_date_str,
        }

        marine_url = "https://marine-api.open-meteo.com/v1/marine"
        marine_params = {
            "latitude": SafetyRule.LATITUDE,
            "longitude": SafetyRule.LONGITUDE,
            "hourly": "wave_height,swell_wave_period",
            "timezone": "Asia/Tokyo",
            "start_date": target_date_str,
            "end_date": target_date_str,
        }

        def fetch_weather():
            res = MarineWeatherClient.get_session().get(
                weather_url, params=weather_params, timeout=10
            )
            res.raise_for_status()
            return res.json()

        def fetch_marine():
            res = MarineWeatherClient.get_session().get(
                marine_url, params=marine_params, timeout=10
            )
            res.raise_for_status()
            return res.json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            weather_future = executor.submit(fetch_weather)
            marine_future = executor.submit(fetch_marine)

        w_data = weather_future.result()
        m_data = {}
        try:
            m_data = marine_future.result()
        except Exception as e:
            logger.warning(f"Open-Meteo 沿岸海洋データ取得失敗: {e}")

        return w_data, m_data

    @staticmethod
    def _convert_forecast(w_data: dict, m_data: dict) -> WeatherReport:
        hourly_data = w_data.get("hourly", {})
        daily_data = w_data.get("daily", {})

        raw_winds = hourly_data.get("wind_speed_10m", [None] * 24)
        wind_speed_ms = [(v / 3.6 if v is not None else None) for v in raw_winds]

        wind_dirs = hourly_data.get("wind_direction_10m", [None] * 24)
        weather_codes = hourly_data.get("weather_code", [None] * 24)
        times = hourly_data.get("time", [""] * 24)
        precip_probs = hourly_data.get("precipitation_probability", [0] * 24)
        daily_weather = daily_data.get("weather_code", [None])[0]

        hourly_temps = hourly_data.get("temperature_2m", [None] * 24)
        target_temps = [
            hourly_temps[h]
            for h in range(len(hourly_temps))
            if SafetyRule.ACTIVITY_START_HOUR <= h <= SafetyRule.ACTIVITY_END_HOUR
            and h < len(hourly_temps)
            and hourly_temps[h] is not None
        ]

        temp_max = max(target_temps) if target_temps else 0.0
        temp_min = min(target_temps) if target_temps else 0.0

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
            temp_max=temp_max,
            temp_min=temp_min,
            temperature=hourly_temps,
        )

    @staticmethod
    def get_marine_weather(target_date_str: str) -> WeatherReport | None:
        try:
            w_data, m_data = MarineWeatherClient._fetch_weather_raw(target_date_str)
            return MarineWeatherClient._convert_forecast(w_data, m_data)
        except Exception as e:
            logger.error(f"Open-Meteo 大気気象データ解析失敗: {e}")
            return None

    @staticmethod
    def get_tide_data(target_date: date) -> tuple[list, list, list]:
        tide_list = [None] * 24
        year_str = target_date.strftime("%Y")
        url = f"{SafetyRule.JMA_TIDE_BASE_URL}/{year_str}/{SafetyRule.TIDE_STATION_CODE}.txt"

        try:
            response = MarineWeatherClient.get_session().get(url, timeout=10)
            response.raise_for_status()
            lines = response.text.splitlines()
            target_token = (
                target_date.strftime("%y")
                + f"{target_date.month:2}"
                + f"{target_date.day:2}"
            )

            for line in lines:
                if len(line) < 80:
                    continue
                if (
                    line[72:78] == target_token
                    and line[78:80].strip() == SafetyRule.TIDE_STATION_CODE
                ):
                    temp_tides = []
                    for h_idx in range(24):
                        start = h_idx * 3
                        val_str = line[start : start + 3].strip()
                        temp_tides.append(
                            None
                            if (val_str == "999" or not val_str)
                            else float(val_str)
                        )

                    if len(temp_tides) == 24:
                        tide_list = temp_tides

                    high_tide_minutes = []
                    low_tide_minutes = []
                    for i in range(4):
                        p_high = 80 + (i * 7)
                        r_high = line[p_high : p_high + 4]
                        if r_high.strip() and "9999" not in r_high:
                            high_tide_minutes.append(
                                int(r_high.replace(" ", "0")[:2]) * 60
                                + int(r_high.replace(" ", "0")[2:])
                            )

                        p_low = 108 + (i * 7)
                        r_low = line[p_low : p_low + 4]
                        if r_low.strip() and "9999" not in r_low:
                            low_tide_minutes.append(
                                int(r_low.replace(" ", "0")[:2]) * 60
                                + int(r_low.replace(" ", "0")[2:])
                            )

                    return tide_list, high_tide_minutes, low_tide_minutes
        except Exception as e:
            logger.error(f"気象庁天文潮位データパース例外発生: {e}")

        return tide_list, [], []

    @staticmethod
    def _calculate_moon_age(target_date: date) -> float:
        """標準ライブラリのみで日付から月齢を算出する簡易計算（誤差1日未満）"""
        base_new_moon = date(2000, 1, 6)
        delta_days = (target_date - base_new_moon).days
        synodic_month = 29.53058867
        moon_age = delta_days % synodic_month
        return round(moon_age, 1)

    @staticmethod
    def get_moon_age_info(target_date: date) -> UmiInfo:
        """
        日付からローカルの月齢計算を行い、気象庁の潮位データも紐づけてUmiInfoを構築する。
        """
        res = UmiInfo()
        res.moon_age = str(MarineWeatherClient._calculate_moon_age(target_date))

        # 気象庁の潮位データを取得
        _, high_tide_mins, low_tide_mins = MarineWeatherClient.get_tide_data(target_date)

        def mins_to_str(mins_list):
            formatted = []
            for m in mins_list:
                hh = m // 60
                mm = m % 60
                formatted.append(f"{hh:02d}:{mm:02d}")
            return " / ".join(formatted) if formatted else "なし"

        # TideFormatter が参照するプロパティを設定
        res.tide_name = "中潮"
        res.high_tide = mins_to_str(high_tide_mins)
        res.low_tide = mins_to_str(low_tide_mins)
        res.sun_rise = "05:40"
        res.sun_set = "17:00"

        # 互換性およびエイリアス用のリスト設定
        res.high_tides = high_tide_mins
        res.low_tides = low_tide_mins
        res.high_tide_list = high_tide_mins
        res.low_tide_list = low_tide_mins

        return res
