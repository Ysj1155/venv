import requests
import json
import logging
from data.data_loader import load_multiple_tickers

# 설정
WATCHLIST_FILE = "watchlist.json"
API_URL = "http://127.0.0.1:5000/get_watchlist"

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_watchlist():
    """
    관심 종목을 Flask API 또는 로컬 JSON에서 로드
    """
    try:
        response = requests.get(API_URL, timeout=3)
        if response.status_code == 200:
            watchlist = response.json().get("watchlist", [])
            save_watchlist(watchlist)
            logging.info(f"✅ 관심 종목 불러옴 (API): {watchlist}")
            return watchlist
        else:
            logging.warning(f"❌ API 응답 실패: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.warning(f"❌ 서버 연결 실패: {e}")

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            watchlist = json.load(f)
            logging.info(f"📁 관심 종목 불러옴 (로컬): {watchlist}")
            return watchlist
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"📁 로컬 관심 종목 로드 실패: {e}")
        return []

def save_watchlist(watchlist):
    """
    관심 종목을 로컬 JSON 파일로 저장
    """
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=4)
        logging.info("📁 관심 종목 저장 완료 (로컬)")
    except Exception as e:
        logging.error(f"❌ 관심 종목 저장 실패: {e}")

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