import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

class WeatherAPI:
    _session = None

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BoatSafetyClient/3.0"})
            retries = Retry(
                total=5, backoff_factor=1.0,
                status_forcelist=[500, 502, 503, 504], raise_on_status=False
            )
            adapter = HTTPAdapter(max_retries=retries)
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session

    @classmethod
    def fetch_text(cls, url: str, params: dict = None) -> str:
        res = cls.get_session().get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.text
