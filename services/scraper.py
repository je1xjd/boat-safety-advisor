import logging
import re
from datetime import date
from bs4 import BeautifulSoup
from engine.models import UmiInfo

logger = logging.getLogger(__name__)

class WeatherScraper:
    @staticmethod
    def parse_umitenki_html(html_text: str, target_date: date) -> UmiInfo:
        """HTML文字列を解析して潮汐情報を抽出する"""
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            date_query = f"{target_date.month}月{target_date.day}日"

            # 特定の日付ブロックを特定
            target_text = ""
            for block in soup.select("div.weather_14days_box"):
                if date_query in (block.select_one("div.weather_14days_date") or "").get_text(""):
                    target_text = block.get_text()
                    break

            if not target_text:
                # フォールバック：全テキストから検索
                pattern = rf"{re.escape(date_query)}\([^)]+\)(.*?)(?=\d+月\d+日|\Z)"
                match = re.search(pattern, soup.get_text(), re.DOTALL)
                target_text = match.group(1) if match else ""

            if not target_text:
                return UmiInfo()

            # データ抽出
            res = UmiInfo()
            if m := re.search(r"【満潮】([\d:/]+)", target_text):
                res.high_tide = m.group(1)
            if m := re.search(r"【干潮】([\d:/]+)", target_text):
                res.low_tide = m.group(1)
            if m := re.search(r"\((大潮|中潮|小潮|長潮|若潮)\)", target_text):
                res.tide_name = m.group(1)
            if m := re.search(r"【月齢】([\d.]+)", target_text):
                res.moon_age = m.group(1)
            if m := re.search(r"【日出/日入】([\d:]+)/([\d:]+)", target_text):
                res.sun_rise, res.sun_set = m.group(1), m.group(2)

            return res

        except Exception as e:
            logger.error(f"解析エラー: {e}")
            return UmiInfo()
