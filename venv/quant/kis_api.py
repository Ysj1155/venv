from config import APP_KEY, APP_SECRET, ACCOUNT_NO
from flask import render_template_string
import plotly.graph_objects as go
import pandas as pd
import pykis
import requests
import http.client
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("appkey")
APP_SECRET = os.getenv("secretkey")
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

kis_token = None
kis_token_expiry = 0

domain_info = pykis.DomainInfo(kind="virtual")
api = pykis.Api(key_info=key_info, domain_info=domain_info, account_info=account_info)

def get_kis_access_token():
    global kis_token, kis_token_expiry

    if kis_token and time.time() < kis_token_expiry - 10:
        print("✅ 기존 access_token 재사용")
        return kis_token

    conn = http.client.HTTPSConnection("openapivts.koreainvestment.com", 29443)
    payload = json.dumps({
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    })
    headers = {
        'content-type': "application/json; charset=UTF-8"
    }
    conn.request("POST", "/oauth2/tokenP", payload, headers)
    res = conn.getresponse()
    data = res.read()
    decoded = json.loads(data.decode("utf-8"))
    print("🔎 access_token response:", decoded)

    if "access_token" in decoded:
        kis_token = decoded["access_token"]
        kis_token_expiry = time.time() + int(decoded["expires_in"])
        return kis_token
    else:
        raise Exception(f"access_token 발급 실패: {decoded}")

def get_overseas_daily_price(ticker, exchange="NAS"):
    token = get_kis_access_token()

    url = f"{URL_BASE}/uapi/overseas-price/v1/quotations/dailyprice"
    headers = {
        "content-type": "application/json; charset=UTF-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "HHDFS76240000",
    }

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

if __name__ == "__main__":
    token = get_kis_access_token()
    print("Access Token:", token)

    # ✅ 해외주식 캔들차트 테스트
    data = get_overseas_daily_price("NVDA", "NAS")
    print(json.dumps(data, indent=2, ensure_ascii=False))
