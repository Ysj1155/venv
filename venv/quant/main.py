import requests
import json
from data.data_loader import load_multiple_tickers

WATCHLIST_FILE = "watchlist.json"
API_URL = "http://127.0.0.1:5000/get_watchlist"  # Flask API URL

def load_watchlist():
    """ 관심 목록을 Flask 서버에서 가져오거나, JSON 파일에서 불러오기 """
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            watchlist = response.json().get("watchlist", [])
            save_watchlist(watchlist)  # ✅ 웹에서 가져온 관심 목록을 로컬에 저장
            return watchlist
    except requests.exceptions.RequestException:
        pass  # 서버 연결 실패 시 로컬 JSON 파일 사용

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # 파일이 없거나 오류 발생 시 빈 목록 반환

def save_watchlist(watchlist):
    """ 웹에서 설정한 관심 목록을 로컬 파일에 저장 """
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    watchlist = load_watchlist()
    print("=== 관심 종목 (웹에서 설정된 종목) ===")
    for stock in watchlist:
        print(stock)

    # ✅ 시장 데이터 로드 (웹 기반 관심 목록 반영)
    GLOBAL_TICKERS = ['AAPL', '^GSPC', 'MSFT'] + watchlist
    KR_TICKERS = ['005930', '000660', '035420']

    load_multiple_tickers(GLOBAL_TICKERS, '2023-01-01', '2025-01-19', market="global")
    load_multiple_tickers(KR_TICKERS, '2023-01-01', '2025-01-19', market="kr")
