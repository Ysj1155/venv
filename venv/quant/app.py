from flask import Flask, render_template, jsonify, request
from markupsafe import Markup
from yahooquery import Ticker
from finnhub_api import (
    get_quote_raw, get_profile_raw, get_metrics_raw,
    get_price_target_raw, get_company_news_raw, get_etf_holdings_raw
)
from kis_api import get_overseas_daily_price
from utils import load_watchlist_file, save_watchlist_file, parse_kis_ohlc
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import requests, markdown
import csv_manager
import json, time, config

app = Flask(__name__)

# ✅ 초기 데이터 로드
csv_manager.process_account_value()
csv_manager.process_portfolio_data()

watchlist = load_watchlist_file()

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
        df = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        columns = ["type", "account_number", "ticker", "profit_loss", "profit_rate",
                   "quantity", "purchase_amount", "evaluation_amount", "evaluation_ratio"]
        return jsonify(df[columns].to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_pie_chart_data")
def get_pie_chart_data():
    try:
        df = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        if df.empty:
            return jsonify({"labels": [], "values": [], "total_value": "0 KRW"})
        total_value = df["evaluation_amount"].sum()
        values = (df["evaluation_amount"] / total_value * 100).tolist()
        return jsonify({
            "labels": df["ticker"].tolist(),
            "values": values,
            "total_value": f"{int(total_value):,} KRW"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    if ticker and ticker not in [t.upper() for t in watchlist]:
        watchlist.append(ticker)
        save_watchlist_file(watchlist)
        return jsonify({"message": "Ticker added", "watchlist": watchlist})
    return jsonify({"error": "Invalid ticker or already exists"}), 400

@app.route("/get_watchlist")
def get_watchlist():
    return jsonify({"watchlist": watchlist})

@app.route("/remove_watchlist", methods=["DELETE"])
def remove_watchlist():
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    if ticker in [t.upper() for t in watchlist]:
        watchlist[:] = [t for t in watchlist if t.upper() != ticker]
        save_watchlist_file(watchlist)
        return jsonify({"message": f"{ticker} removed", "watchlist": watchlist})
    return jsonify({"error": "Ticker not found"}), 400

@app.route("/get_account_value_data")
def get_account_value_data():
    try:
        df = pd.read_csv(csv_manager.ACCOUNT_VALUE_FILE, encoding="utf-8-sig")
        initial_value = 23529530
        df["profit"] = ((df["total_value"] - initial_value) / initial_value) * 100
        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "total_values": df["total_value"].tolist(),
            "profits": df["profit"].tolist(),
            "latest_value": df.iloc[-1]["total_value"],
            "latest_profit": df.iloc[-1]["profit"]
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
        df_sp500 = fdr.StockListing("S&P500")[["Symbol", "Sector"]]
        df_sp500.rename(columns={"Symbol": "converted_ticker"}, inplace=True)
        ticker_map = {
            "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA",
            "알파벳 A": "GOOGL", "아마존닷컴": "AMZN",
            "카디널 헬스": "CAH", "TSMC(ADR)": "TSM",
            "PROETF ULTRAPRO QQQ": "TQQQ", "INVESCO QQQ TRUST UNIT SER 1": "QQQ"
        }
        df = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        df["converted_ticker"] = df["ticker"].map(ticker_map).fillna("Unknown")
        df["evaluation_amount"] = df["evaluation_amount"].fillna(0)
        df = df.merge(df_sp500, on="converted_ticker", how="left")
        df["Sector"] = df["Sector"].fillna("Non-S&P 500")

        result = {}
        for sector, group in df.groupby("Sector"):
            stocks = [{"ticker": row["converted_ticker"], "price": row["evaluation_amount"]} for _, row in group.iterrows()]
            result[sector] = {
                "total_value": group["evaluation_amount"].sum(),
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
