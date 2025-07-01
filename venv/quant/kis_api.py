from config import APP_KEY, APP_SECRET, ACCOUNT_NO
from flask import render_template_string
import plotly.graph_objects as go
import pandas as pd
import pykis
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("APP_KEY")
APP_Secret = os.getenv("APP_SECRET")
URL_BASE = "https://openapivts.koreainvestment.com:29443"

# 계좌번호 split
ACCOUNT_CODE = ACCOUNT_NO.split('-')[0]
PRODUCT_CODE = ACCOUNT_NO.split('-')[1]

key_info = {
    "appkey": APP_KEY,
    "appsecret": APP_SECRET
}

account_info = {
    "account_code": ACCOUNT_CODE,
    "product_code": PRODUCT_CODE
}

domain_info = pykis.DomainInfo(kind="virtual")
api = pykis.Api(key_info=key_info, domain_info=domain_info, account_info=account_info)

def get_kis_access_token():
    """
    한국투자증권 Open API access token 발급 함수
    """
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    URL = f"{URL_BASE}/oauth2/tokenP"

    res = requests.post(URL, headers=headers, data=json.dumps(body))
    res.raise_for_status()
    ACCESS_TOKEN = res.json()["access_token"]
    return ACCESS_TOKEN

def get_overseas_daily_price(ticker, exchange="NAS"):
    """
    해외주식 기간별시세 (캔들차트) API 호출 함수
    """
    token = get_kis_access_token()

    url = f"{URL_BASE}/uapi/overseas-price/v1/quotations/dailyprice"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "HHDFS76240000",
    }
    import time
    now = time.strftime("%Y%m%d")
    params = {
        "AUTH": "",
        "EXCD": exchange,
        "SYMB": ticker,
        "GUBN": "0",  # 일봉
        "BYMD": now,
        "MODP": "1"
    }

    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()