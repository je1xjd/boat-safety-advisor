"""
weather.py

HTTP通信およびリトライロジックを管理するAPIクライアント基盤。
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import Optional

class WeatherAPI:
    """外部APIとの通信を統括するシングルトン・セッション管理クラス。"""
    
    _session: Optional[requests.Session] = None
    
    # 共通設定を定数化
    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoatSafetyClient/3.0"
    _TIMEOUT = 10

    @classmethod
    def get_session(cls) -> requests.Session:
        """既存のセッションを返すか、なければ新規作成して返す。"""
        if cls._session is None:
            cls._session = cls._create_session()
        return cls._session

    @classmethod
    def _create_session(cls) -> requests.Session:
        """リトライ設定付きのHTTPセッションを生成する。"""
        session = requests.Session()
        session.headers.update({"User-Agent": cls._USER_AGENT})
        
        # 指数バックオフによるリトライ設定
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

    @classmethod
    def fetch_text(cls, url: str, params: Optional[dict] = None) -> str:
        """指定されたURLから文字列を取得する。通信エラー時は例外を発生させる。"""
        response = cls.get_session().get(url, params=params, timeout=cls._TIMEOUT)
        response.raise_for_status()
        return response.text
