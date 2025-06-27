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
    return requests.get(url, params=params).json()

# 회사 프로필 원본
def get_profile_raw(ticker):
    url = f"{BASE_URL}/stock/profile2"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return requests.get(url, params=params).json()

# 재무 지표 원본
def get_metrics_raw(ticker):
    url = f"{BASE_URL}/stock/metric"
    params = {"symbol": ticker, "metric": "all", "token": FINNHUB_API_KEY}
    return requests.get(url, params=params).json()

# 목표가 원본
def get_price_target_raw(ticker):
    url = f"{BASE_URL}/stock/price-target"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return requests.get(url, params=params).json()

# 뉴스 원본
def get_company_news_raw(ticker, from_date, to_date):
    url = f"{BASE_URL}/company-news"
    params = {
        "symbol": ticker,
        "from": from_date,
        "to": to_date,
        "token": FINNHUB_API_KEY
    }
    return requests.get(url, params=params).json()

# ETF 구성 종목 원본
def get_etf_holdings_raw(ticker):
    url = f"{BASE_URL}/etf/holdings"
    params = {"symbol": ticker, "token": FINNHUB_API_KEY}
    return requests.get(url, params=params).json()

