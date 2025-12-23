import requests
import logging
from data.data_loader import load_multiple_tickers

API_URL = "http://127.0.0.1:5000/get_watchlist"  # ✅ Flask API URL

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_watchlist():
    """
    관심 종목을 Flask API에서 로드
    """
    try:
        response = requests.get(API_URL, timeout=3)
        response.raise_for_status()
        watchlist = response.json().get("watchlist", [])
        logging.info(f"✅ 관심 종목 불러옴 (API): {watchlist}")
        return watchlist
    except requests.exceptions.RequestException as e:
        logging.warning(f"❌ 관심 종목 불러오기 실패: {e}")
        return []

def run():
    """
    관심 종목 로드 후 시장 데이터 수집 실행
    """
    watchlist = load_watchlist()

    GLOBAL_TICKERS = sorted(set(['AAPL', '^GSPC', 'MSFT'] + watchlist))
    KR_TICKERS = ['005930', '000660', '035420']

    logging.info(f"🌐 글로벌 종목 수집 시작: {GLOBAL_TICKERS}")
    load_multiple_tickers(GLOBAL_TICKERS, '2023-01-01', '2025-01-19', market="global")

    logging.info(f"🇰🇷 국내 종목 수집 시작: {KR_TICKERS}")
    load_multiple_tickers(KR_TICKERS, '2023-01-01', '2025-01-19', market="kr")

if __name__ == "__main__":
    run()