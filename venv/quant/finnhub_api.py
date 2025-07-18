import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from config import FINNHUB_API_KEY

BASE_URL = "https://finnhub.io/api/v1"

# 공통 안전 요청 함수
def safe_request(url, params):
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ 요청 실패: {url} -> {e}")
        return {"error": str(e)}

# 현재가 원본
def get_quote_raw(ticker):
    url = f"{BASE_URL}/quote"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return safe_request(url, params)

# 회사 프로필 원본
def get_profile_raw(ticker):
    url = f"{BASE_URL}/stock/profile2"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return safe_request(url, params)

# 재무 지표 원본
def get_metrics_raw(ticker):
    url = f"{BASE_URL}/stock/metric"
    params = {"symbol": ticker, "metric": "all", "token": FINNHUB_API_KEY}
    return safe_request(url, params)

# 목표가 원본
def get_price_target_raw(ticker):
    url = f"{BASE_URL}/stock/price-target"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return safe_request(url, params)

# 뉴스 원본
def get_company_news_raw(ticker, from_date, to_date):
    url = f"{BASE_URL}/company-news"
    params = {
        "symbol": ticker,
        "from": from_date,
        "to": to_date,
        "token": FINNHUB_API_KEY
    }
    return safe_request(url, params)

# ETF 구성 종목 원본
def get_etf_holdings_raw(ticker):
    url = f"{BASE_URL}/etf/holdings"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return safe_request(url, params)

# 캔들 데이터
def get_candle_data(ticker, days=90):
    now = int(time.time())
    past = now - 60 * 60 * 24 * days
    url = f"{BASE_URL}/stock/candle"
    params = {
        "symbol": ticker,
        "resolution": "D",
        "from": past,
        "to": now,
        "token": FINNHUB_API_KEY
    }
    res = safe_request(url, params)
    if res.get("s") != "ok":
        print(f"❌ 캔들 응답 실패: {res}")
        return None
    df = pd.DataFrame({
        "timestamp": res["t"],
        "close": res["c"]
    })
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df[df['date'].dt.dayofweek < 5]
    return df

# 기술 지표 계산 (MA5, MA20, RSI)
def calculate_indicators(df):
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    df.dropna(inplace=True)
    return df

# 회사 뉴스 자동 기간 버전
def get_company_news_auto(ticker, days=7):
    to_date = datetime.today().date()
    from_date = to_date - timedelta(days=days)
    return get_company_news_raw(ticker, from_date.isoformat(), to_date.isoformat())