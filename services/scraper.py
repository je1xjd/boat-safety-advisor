from bs4 import BeautifulSoup
import re
from engine.models import UmiInfo
import logging

logger = logging.getLogger(__name__)

class WeatherScraper:
    @staticmethod
    def parse_umitenki_html(html_text: str, target_date) -> UmiInfo:
        """通信済みのHTML文字列を受け取り、パース処理のみを行う"""
        default_res = UmiInfo()
        
        try:
            # 引数の html_text を使う
            soup = BeautifulSoup(html_text, "html.parser")
            day_blocks = soup.select("div.weather_14days_box")
        
            target_block_text = None
            date_query_text = f"{target_date.month}月{target_date.day}日"

            for block in day_blocks:
                title_elem = block.select_one("div.weather_14days_date")
                if title_elem and date_query_text in title_elem.get_text():
                    target_block_text = block.get_text()
                    break

            if not target_block_text:
                html_text_raw = soup.get_text()
                pattern = rf"{re.escape(date_query_text)}\([^)]+\)(.*?)(?=\d+月\d+日|\Z)"
                match = re.search(pattern, html_text_raw, re.DOTALL)
                if match:
                    target_block_text = match.group(1)

            if not target_block_text:
                return default_res
            
            # 解析結果を格納するインスタンス
            res = UmiInfo()
        
            high_match = re.search(r"【満潮】([\d:/]+)", target_block_text)
            if high_match: res.high_tide = high_match.group(1)
            
            low_match = re.search(r"【干潮】([\d:/]+)", target_block_text)
            if low_match: res.low_tide = low_match.group(1)
        
            name_match = re.search(r"\((大潮|中潮|小潮|長潮|若潮)\)", target_block_text)
            if name_match: res.tide_name = name_match.group(1)
            
            moon_match = re.search(r"【月齢】([\d.]+)", target_block_text)
            if moon_match: res.moon_age = moon_match.group(1)
            
            sun_match = re.search(r"【日出/日入】([\d:]+)/([\d:]+)", target_block_text)
            if sun_match:
                res.sun_rise = sun_match.group(1)
                res.sun_set = sun_match.group(2)
            
            return res

        except Exception as e:
            logger.error(f"解析レイヤーで例外を検出: {e}")
            return default_res
