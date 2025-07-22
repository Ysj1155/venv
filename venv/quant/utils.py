import json
from db.db import get_connection
WATCHLIST_PATH = "watchlist.json"

def load_watchlist_file():
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT ticker FROM watchlist ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [r["ticker"] for r in rows]
    except Exception as e:
        print(f"❌ watchlist 불러오기 실패: {e}")
        return []

def save_watchlist_file(tickers):
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM watchlist")  # 기존 전체 삭제
            for ticker in tickers:
                cur.execute("INSERT INTO watchlist (ticker) VALUES (%s)", (ticker,))
            conn.commit()
    except Exception as e:
        print(f"❌ watchlist 저장 실패: {e}")

def parse_kis_ohlc(data):
    items = data.get("output2", [])
    ohlc = []
    for item in reversed(items):  # 날짜 오름차순
        date = item.get("xymd")
        open_ = item.get("open")
        high = item.get("high")
        low = item.get("low")
        close = item.get("clos")
        volume = item.get("tvol")

        if None in (date, open_, high, low, close, volume):
            continue

        try:
            ohlc.append({
                "date": date,
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume)
            })
        except (ValueError, TypeError):
            continue
    return ohlc