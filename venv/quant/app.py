from flask import Flask, render_template, jsonify, request
from markupsafe import Markup
from yahooquery import Ticker
from api.finnhub_api import (
    get_quote_raw, get_profile_raw, get_metrics_raw,
    get_price_target_raw, get_company_news_raw, get_etf_holdings_raw
)
from api.kis_api import get_overseas_daily_price
from utils import parse_kis_ohlc, get_connection
from db.migration import migrate_portfolio, migrate_account_value
from data.csv_manager import process_account_value, process_portfolio_data
from functools import lru_cache
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import requests, markdown
import data.csv_manager
import json, time, config

app = Flask(__name__)
bootstrap_refresh()
AUTO_REFRESH_CSV = os.getenv("AUTO_REFRESH_CSV", "true").lower() in ("1", "true", "yes", "y")

# 앱 시작 직후에 한 번 실행
def bootstrap_refresh():
    """1) data/*.csv 원본 → 중간산출물 생성  2) DB 마이그레이션"""
    if not AUTO_REFRESH_CSV:
        print("ℹ️ AUTO_REFRESH_CSV=FALSE → CSV 갱신 스킵")
        return

    print("🔄 CSV 재생성 시작")
    process_account_value()
    process_portfolio_data()
    print("✅ CSV 재생성 완료")

    print("🔄 DB 마이그레이션 시작")
    migrate_portfolio()
    migrate_account_value()
    print("✅ DB 마이그레이션 완료")

# 앱 실행 전 자동 마이그레이션
try:
    migrate_portfolio()
    migrate_account_value()
    print("✅ DB 자동 마이그레이션 완료")
except Exception as e:
    print(f"❌ 마이그레이션 오류: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/readme")
def show_readme():
    with open("readme.md", "r", encoding="utf-8") as f:
        content = f.read()
        html = markdown.markdown(content)
        return f"<div style='padding:40px;'>{Markup(html)}</div>"

@app.route("/get_portfolio_data")
def get_portfolio_data():
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("""
                SELECT account_number, ticker, quantity,
                       purchase_amount, evaluation_amount,
                       profit_loss, profit_rate, evaluation_ratio
                FROM portfolio
            """)
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_pie_chart_data")
def get_pie_chart_data():
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT ticker, evaluation_amount FROM portfolio")
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return jsonify({"labels": [], "values": [], "total_value": "0 KRW"})
        tickers = [row["ticker"] for row in rows]
        amounts = [row["evaluation_amount"] for row in rows]
        total = sum(amounts)
        values = [(amt / total) * 100 if total else 0 for amt in amounts]
        return jsonify({
            "labels": tickers,
            "values": values,
            "total_value": f"{int(total):,} KRW"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    if not ticker:
        return jsonify({"error": "티커가 유효하지 않습니다"}), 400
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM watchlist WHERE ticker = %s", (ticker,))
            exists = cur.fetchone()["count"]
            if exists:
                conn.close()
                return jsonify({"error": "이미 등록된 티커입니다"}), 400
            cur.execute("INSERT INTO watchlist (ticker) VALUES (%s)", (ticker,))
            conn.commit()
            cur.execute("SELECT ticker FROM watchlist ORDER BY created_at DESC")
            tickers = [r["ticker"] for r in cur.fetchall()]
        conn.close()
        return jsonify({"message": "추가 완료", "watchlist": tickers})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_watchlist")
def get_watchlist():
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT ticker FROM watchlist ORDER BY created_at DESC")
            rows = cur.fetchall()
        conn.close()
        tickers = [row["ticker"] for row in rows]
        return jsonify({"watchlist": tickers})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/remove_watchlist", methods=["DELETE"])
def remove_watchlist():
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("DELETE FROM watchlist WHERE ticker = %s", (ticker,))
            conn.commit()
            cur.execute("SELECT ticker FROM watchlist ORDER BY created_at DESC")
            tickers = [r["ticker"] for r in cur.fetchall()]
        conn.close()
        return jsonify({"message": f"{ticker} 삭제됨", "watchlist": tickers})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_account_value_data")
def get_account_value_data():
    try:
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT date, total_value FROM account_value ORDER BY date ASC")
            rows = cur.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "No account value data found"}), 500

        dates = [str(row["date"]) for row in rows]
        values = [row["total_value"] for row in rows]
        base = values[0]
        profits = [(v - base) / base * 100 for v in values]

        return jsonify({
            "dates": dates,
            "total_values": values,
            "profits": profits,
            "latest_value": values[-1],
            "latest_profit": profits[-1]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_treemap_data")
def get_treemap_data():
    try:
        sectors = {
            "Technology": "XLK", "Financials": "XLF", "Communication": "XLC",
            "Healthcare": "XLV", "Consumer Discretionary": "XLY", "Consumer Defensive": "XLP",
            "Industrials": "XLI", "Real Estate": "XLRE", "Energy": "XLE",
            "Utilities": "XLU", "Materials": "XLB"
        }
        sector_data = []
        for sector, ticker in sectors.items():
            df = fdr.DataReader(ticker, "2023")
            df["Change"] = ((df["Close"] - df["Close"].shift(1)) / df["Close"].shift(1)) * 100
            latest_change = df["Change"].iloc[-1]
            sector_data.append({"Sector": sector, "Change": latest_change})
        df_sectors = pd.DataFrame(sector_data)
        return jsonify({
            "sectors": df_sectors["Sector"].tolist(),
            "changes": df_sectors["Change"].tolist()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 한글/표기 혼용 티커 보정 (필요 시 확장)
TICKER_MAP = {
    "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA",
    "알파벳 A": "GOOGL", "아마존닷컴": "AMZN",
    "TSMC(ADR)": "TSM", "카디널 헬스": "CAH",
    "PROSHARES QQQ 3X": "TQQQ", "INVESCO QQQ TRUST UNIT SER 1": "QQQ"
}

def normalize_symbol(raw: str) -> str | None:
    if not raw:
        return None
    raw = str(raw).strip()
    # 1) 사전 매핑 우선
    if raw in TICKER_MAP:
        return TICKER_MAP[raw]
    # 2) 완전 영문/숫자/점(.)만 허용(야후 티커 규칙 대략)
    t = raw.upper()
    if all(ch.isalnum() or ch == '.' or ch == '-' for ch in t):
        return t
    # 그 외(한글/공백/특수문자 등)는 사용 불가로 간주 → None
    return None

@lru_cache(maxsize=1024)
def is_etf(symbol: str) -> bool:
    try:
        qt = Ticker(symbol).quote_type
        if isinstance(qt, dict) and symbol in qt:
            return (qt[symbol].get("quoteType") == "ETF")
    except Exception:
        pass
    return False

# Yahoo의 sector 키는 소문자/띄어쓰기 다를 수 있어 → 표준 GICS 표기로 정규화
SECTOR_NORMALIZE = {
    "basic materials": "Materials",
    "communication services": "Communication Services",
    "consumer cyclical": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "energy": "Energy",
    "financial services": "Financials",
    "financial": "Financials",
    "healthcare": "Healthcare",
    "industrials": "Industrials",
    "real estate": "Real Estate",
    "technology": "Information Technology",
    "information technology": "Information Technology",
    "utilities": "Utilities",
}

def norm_sector_name(s: str) -> str:
    key = (s or "").strip().lower()
    return SECTOR_NORMALIZE.get(key, s or "Unknown")

@lru_cache(maxsize=256)
def get_etf_sector_weights(symbol: str) -> dict[str, float] | None:
    """
    ETF 섹터 비중값을 {섹터명: 가중치(0~1)}로 반환.
    yahooquery.fund_sector_weightings는 [{"technology": 45.67, ...}] 형태.
    """
    try:
        data = Ticker(symbol).fund_sector_weightings
        # yahooquery는 종종 dict / list 섞여옴 → 유연하게 처리
        if isinstance(data, dict) and "sectorWeightings" in data:
            rows = data["sectorWeightings"]
        else:
            rows = data
        if not rows:
            return None
        if isinstance(rows, list):
            row = rows[0] if rows else {}
        elif isinstance(rows, dict):
            row = rows
        else:
            return None

        weights = {}
        for k, v in row.items():
            try:
                w = float(v)
            except Exception:
                continue
            if w <= 0:
                continue
            weights[norm_sector_name(k)] = w / 100.0
        s = sum(weights.values()) or 1.0
        # 합이 1이 아니면 정규화
        return {k: w / s for k, w in weights.items()} if weights else None
    except Exception:
        return None

@lru_cache(maxsize=2048)
def get_sector_for_symbol(symbol: str) -> str:
    """개별 종목 섹터 (ETF 아님). Yahoo 우선, 실패 시 Finnhub 보조."""
    # 1) Yahoo profile
    try:
        prof = Ticker(symbol).asset_profile
        if isinstance(prof, dict) and symbol in prof:
            sec = prof[symbol].get("sector")
            if sec:
                return norm_sector_name(sec)
    except Exception:
        pass
    # 2) Finnhub fallback
    try:
        prof2 = get_profile_raw(symbol)
        if isinstance(prof2, dict):
            sec = prof2.get("finnhubIndustry")
            if sec:
                return norm_sector_name(sec)
    except Exception:
        pass
    return "Unknown"

def add_to_bucket(bucket: dict, sector: str, sym: str, value: float):
    if sector not in bucket:
        bucket[sector] = {"total_value": 0, "stocks": []}
    bucket[sector]["total_value"] += int(value)
    bucket[sector]["stocks"].append({"ticker": sym, "price": int(value)})

@lru_cache(maxsize=256)
def get_etf_holdings(symbol: str):
    """
    ETF 보유목록을 (symbol, weight) 리스트로 반환 (weight: 0~1).
    holdings가 없으면 None -> ETF 아님으로 취급.
    """
    try:
        raw = get_etf_holdings_raw(symbol)
        holds = raw.get("holdings")
        if not holds:
            return None
        # finnhub는 weight가 % 단위(예: 12.34)로 올 때가 많음
        items = []
        for h in holds:
            hs = h.get("symbol") or h.get("name") or ""
            w = h.get("weight")
            if hs and w is not None:
                try:
                    w = float(w)
                except Exception:
                    continue
                items.append((normalize_symbol(hs), w / 100.0))
        # 정규화(혹시 합이 약간 안 맞을 때)
        s = sum(w for _, w in items) or 1.0
        items = [(sym, w / s) for sym, w in items]
        return items if items else None
    except Exception:
        return None

@app.route("/get_portfolio_sector_data")
def get_portfolio_sector_data():
    """
    포트폴리오(개별주식 + ETF)를 섹터 기준으로 look-through.
    - ETF: ETF의 섹터 비중(fund_sector_weightings) 그대로 평가금액에 곱해 분해
    - 개별주식: 심볼 섹터 조회 후 더함
    응답: { sector: { total_value, stocks: [ {ticker, price}, ... ] }, ... }
    """
    try:
        # 1) DB에서 평가금액 로드
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT ticker, evaluation_amount FROM portfolio")
            rows = cur.fetchall()
        conn.close()

        if not rows:
            return jsonify({})

        bucket = {}

        for r in rows:
            raw = r["ticker"]
            eval_amt = r["evaluation_amount"] or 0
            try:
                eval_amt = float(eval_amt)
            except Exception:
                continue

            sym = normalize_symbol(raw)
            if not sym:
                # 한글 등으로 심볼 매핑이 안되면 건너뜀(섹터 Unknown으로 버킷 오염 방지)
                continue

            if is_etf(sym):
                # 2) ETF → 섹터 가중치로 직접 분해
                weights = get_etf_sector_weights(sym)
                if weights:
                    for sector, w in weights.items():
                        add_to_bucket(bucket, sector, sym, eval_amt * w)
                else:
                    # 섹터 가중치 없으면 최후 fallback: ETF 전체를 Unknown으로 분류
                    add_to_bucket(bucket, "Unknown", sym, eval_amt)
            else:
                # 3) 개별주식 → 섹터 직접 매핑
                sector = get_sector_for_symbol(sym)
                add_to_bucket(bucket, sector, sym, eval_amt)

        return jsonify(bucket)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_exchange_rate_data")
def get_exchange_rate_data():
    try:
        df = fdr.DataReader('USD/KRW', '2023')[['Close']].reset_index()
        df.rename(columns={'Close': 'exchange_rate', 'index': 'date'}, inplace=True)
        df = df.dropna(subset=['exchange_rate'])
        df = df[~df["date"].dt.strftime('%m-%d').eq("01-01")]
        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "rates": df["exchange_rate"].tolist()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_stock_detail_finnhub")
def get_stock_detail_finnhub():
    ticker = request.args.get("ticker", "").upper()
    return jsonify({
        "ticker": ticker,
        "price": get_quote_raw(ticker),
        "profile": get_profile_raw(ticker),
        "metrics": get_metrics_raw(ticker)
    })

@app.route("/get_stock_chart_kis")
def get_stock_chart_kis():
    ticker = request.args.get("ticker")
    exchange = request.args.get("exchange", "NAS")
    try:
        raw = get_overseas_daily_price(ticker, exchange)
        return jsonify({"ohlc": parse_kis_ohlc(raw)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == "__main__":
    app.run(debug=True)
