from flask import Flask, render_template, jsonify, request
from markupsafe import Markup
from yahooquery import Ticker
from api.finnhub_api import (
    get_quote_raw, get_profile_raw, get_metrics_raw,
    get_price_target_raw, get_company_news_raw, get_etf_holdings_raw
)
from api.kis_api import get_overseas_daily_price
from utils import load_watchlist_file, save_watchlist_file, parse_kis_ohlc
from db.db import get_connection
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import requests, markdown
import data.csv_manager
import json, time, config

app = Flask(__name__)

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

@app.route("/get_portfolio_sector_data")
def get_portfolio_sector_data():
    try:
        # 1. 영문 티커 매핑 딕셔너리
        ticker_map = {
            "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA",
            "알파벳 A": "GOOGL", "아마존닷컴": "AMZN",
            "TSMC(ADR)": "TSM", "카디널 헬스": "CAH",
            "PROSHARES QQQ 3X": "TQQQ", "INVESCO QQQ TRUST UNIT SER 1": "QQQ"
        }
        # 2. DB에서 포트폴리오 가져오기
        conn = get_connection()
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT ticker, evaluation_amount FROM portfolio")
            rows = cur.fetchall()
        conn.close()
        if not rows:
            return jsonify({})
        df = pd.DataFrame(rows)
        df["converted_ticker"] = df["ticker"].map(ticker_map).fillna("Unknown")
        # 3. S&P500 섹터 정보 로딩
        df_sp500 = fdr.StockListing("S&P500")[["Symbol", "Sector"]]
        df_sp500.rename(columns={"Symbol": "converted_ticker"}, inplace=True)
        df = df.merge(df_sp500, on="converted_ticker", how="left")
        df["Sector"] = df["Sector"].fillna("Non-S&P 500")
        # 4. 섹터별 정리
        result = {}
        for sector, group in df.groupby("Sector"):
            stocks = [
                {"ticker": row["converted_ticker"], "price": int(row["evaluation_amount"])}
                for _, row in group.iterrows()
            ]
            result[sector] = {
                "total_value": int(group["evaluation_amount"].sum()),
                "stocks": stocks
            }
        return jsonify(result)
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
