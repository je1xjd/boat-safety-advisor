"""
scraper.py

WebサイトからのHTML解析・データ抽出サービス。
"""

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from engine.models import UmiInfo

logger = logging.getLogger(__name__)


class WeatherScraper:
    """HTMLから海象・潮汐情報を抽出する。"""

    @staticmethod
    def _calculate_moon_age(target_date: date) -> float:
        """標準ライブラリのみで日付から月齢を算出する簡易計算（誤差1日未満）"""
        base_new_moon = date(2000, 1, 6)
        delta_days = (target_date - base_new_moon).days
        synodic_month = 29.53058867
        moon_age = delta_days % synodic_month
        return round(moon_age, 1)

    @staticmethod
    def parse_umitenki_html(html_text: str, target_date: date) -> UmiInfo:
        """HTML文字列を解析し、指定日の情報を抽出する。"""
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            date_query = f"{target_date.month}月{target_date.day}日"

            target_text = ""
            for block in soup.select("section.forecast-day, div.weather_14days_box, .forecast-box, article, section, div"):
                block_text = block.get_text()
                if date_query in block_text and len(block_text) < 3000:
                    target_text = block_text
                    break

            if not target_text:
                for element in soup.find_all(string=re.compile(re.escape(date_query))):
                    parent = element.parent
                    for _ in range(4):
                        if parent and len(parent.get_text()) > 30:
                            target_text = parent.get_text()
                            break
                        if parent:
                            parent = parent.parent
                    if target_text:
                        break

            if not target_text:
                res = UmiInfo()
                res.moon_age = str(WeatherScraper._calculate_moon_age(target_date))
                return res

            res = UmiInfo()

            # 潮汐名の抽出
            if m := re.search(r"(大潮|中潮|小潮|長潮|若潮)", target_text):
                res.tide_name = m.group(1)

            # 満潮・干潮時刻の抽出
            if m := re.search(r"(?:【満潮】|\[満潮\]|満潮)[:：]?\s*([\d:/]+)", target_text):
                res.high_tide = m.group(1).strip()
            if m := re.search(r"(?:【干潮】|\[干潮\]|干潮)[:：]?\s*([\d:/]+)", target_text):
                res.low_tide = m.group(1).strip()

            # 【月齢のハイブリッド取得】
            # 1. サイトのHTML内に数値があればそれを優先取得
            parsed_moon_age = None
            if m := re.search(r"(?:【月齢】|\[月齢\]|月齢)[\s:：]*([\d.]+)", target_text):
                parsed_moon_age = m.group(1)

            # 2. 取得できなかった場合（または "--" の場合）、自動計算した値でフォールバック
            if parsed_moon_age and parsed_moon_age != "--":
                res.moon_age = parsed_moon_age
            else:
                res.moon_age = str(WeatherScraper._calculate_moon_age(target_date))

            # 日出・日入の抽出
            if m := re.search(r"(?:日出[し]?/日入[り]?|日の出/日の入り|日出/日入|【日出/日入】)[:：]?\s*([\d:]+)[/\s|]+(?:日の入り|日入)?\s*([\d:]+)", target_text):
                res.sun_rise, res.sun_set = m.group(1), m.group(2)
            else:
                if m_rise := re.search(r"(?:日の出|日出)[:：]?\s*([\d:]+)", target_text):
                    res.sun_rise = m_rise.group(1)
                if m_set := re.search(r"(?:日の入り|日入)[:：]?\s*([\d:]+)", target_text):
                    res.sun_set = m_set.group(1)

            return res

        except Exception as e:
            logger.error(f"解析エラー: {e}")
            res = UmiInfo()
            res.moon_age = str(WeatherScraper._calculate_moon_age(target_date))
            return res
