from flask import Flask, render_template, jsonify, request  # Flask 기본 기능
from markupsafe import Markup                      # Markdown HTML 안전 처리
from yahooquery import Ticker
from finnhub_api import get_quote, get_candle_data, calculate_indicators
import FinanceDataReader as fdr
import pandas as pd
import requests, markdown                          # API 요청 + Markdown to HTML
import csv_manager                                  # CSV 데이터 처리 모듈
import json

app = Flask(__name__)

# ✅ 서버 시작 시 CSV 데이터 최신화
csv_manager.process_account_value()
csv_manager.process_portfolio_data()

@app.route("/readme")
def show_readme():
    with open("readme.md", "r", encoding="utf-8") as f:
        content = f.read()
        html = markdown.markdown(content)  # Markdown → HTML 변환
        return f"<div style='padding:40px;'>{Markup(html)}</div>"

@app.route("/")
def index():
    return render_template("index.html")
    """ 메인 페이지 렌더링 """

@app.route("/get_portfolio_data", methods=["GET"])
def get_portfolio_data():
    """ 포트폴리오 데이터를 JSON 형식으로 반환하는 엔드포인트 """
    try:
        df = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        columns = ["type", "account_number", "ticker", "profit_loss", "profit_rate", "quantity", "purchase_amount", "evaluation_amount", "evaluation_ratio"]
        df = df[columns]
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_pie_chart_data", methods=["GET"])
def get_pie_chart_data():
    """ 최신 날짜 기준으로 원형 차트 데이터를 반환하는 엔드포인트 """
    try:
        df = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        if df.empty or "evaluation_amount" not in df.columns or "ticker" not in df.columns:
            return jsonify({"labels": [], "values": [], "total_value": "0 KRW"})
        total_value = df["evaluation_amount"].sum()
        if total_value <= 0:
            return jsonify({"labels": [], "values": [], "total_value": "0 KRW"})
        return jsonify({
            "labels": df["ticker"].tolist(),
            "values": (df["evaluation_amount"] / total_value * 100).tolist(),
            "total_value": f"{int(total_value):,} KRW"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

watchlist = []  # 관심 종목 리스트
@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    data = request.get_json()
    ticker = data.get("ticker").upper()
    if ticker and ticker not in [t.upper() for t in watchlist]:
        watchlist.append(ticker)
        save_watchlist_file(watchlist)  # ← 저장!
        return jsonify({"message": "Ticker added", "watchlist": watchlist})
    else:
        return jsonify({"error": "Invalid ticker or already exists"}), 400

@app.route("/get_watchlist", methods=["GET"])
def get_watchlist():
    """현재 저장된 관심 종목 리스트 반환"""
    return jsonify({"watchlist": watchlist})

WATCHLIST_PATH = "watchlist.json"

def load_watchlist_file():
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_watchlist_file(watchlist):
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

@app.route("/remove_watchlist", methods=["DELETE"])
def remove_watchlist():
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    if ticker in [t.upper() for t in watchlist]:
        # 대소문자 일치 항목 삭제
        watchlist[:] = [t for t in watchlist if t.upper() != ticker]
        save_watchlist_file(watchlist)
        return jsonify({"message": f"{ticker} removed", "watchlist": watchlist})
    else:
        return jsonify({"error": "Ticker not found"}), 400

# 서버 시작 시 로드
watchlist = load_watchlist_file()

@app.route("/get_account_value_data", methods=["GET"])
def get_account_value_data():
    """ 날짜별 총 평가금액 및 지정된 금액(23,529,530) 대비 수익률 데이터를 반환하는 엔드포인트 """
    try:
        df = pd.read_csv(csv_manager.ACCOUNT_VALUE_FILE, encoding="utf-8-sig")
        # ✅ 필수 컬럼 확인
        if "date" not in df.columns or "total_value" not in df.columns:
            return jsonify({"error": "CSV 파일에 'date' 또는 'total_value' 컬럼이 없습니다."}), 400
        # ✅ 하드코딩된 기준 평가금액
        initial_value = 23529530  # 사용자가 지정한 기준 금액
        # ✅ 지정된 금액 대비 수익률(%) 계산
        df["profit"] = ((df["total_value"] - initial_value) / initial_value) * 100
        latest_value = df.iloc[-1]["total_value"]
        latest_profit = df.iloc[-1]["profit"]
        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "total_values": df["total_value"].tolist(),  # 총 평가금액
            "profits": df["profit"].tolist(),  # 기준 금액(23,529,530) 대비 수익률 (%)
            "latest_value": latest_value,
            "latest_profit": latest_profit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_treemap_data", methods=["GET"])
def get_treemap_data():
    """ S&P 500 섹터별 변동률 및 내 포트폴리오 비교 데이터를 반환하는 엔드포인트 """
    try:
        # ✅ 11개 섹터 ETF 데이터 가져오기
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
            latest_change = df["Change"].iloc[-1]  # 최신 변화율
            sector_data.append({"Sector": sector, "Change": latest_change})
        df_sectors = pd.DataFrame(sector_data)
        return jsonify({
            "sectors": df_sectors["Sector"].tolist(),
            "changes": df_sectors["Change"].tolist()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_portfolio_sector_data", methods=["GET"])
def get_portfolio_sector_data():
    """ 내 포트폴리오의 섹터별 평가금액 비율 및 각 섹터별 포함 종목 정보를 반환하는 엔드포인트 """
    try:
        # ✅ S&P 500 데이터 가져오기
        df_sp500 = fdr.StockListing("S&P500")[["Symbol", "Name", "Sector"]]
        df_sp500.rename(columns={"Symbol": "converted_ticker"}, inplace=True)
        # ✅ 한글 종목명을 영어 Symbol로 매핑
        ticker_mapping = {
            "애플": "AAPL", "엔비디아": "NVDA", "테슬라": "TSLA",
            "알파벳 A": "GOOGL", "아마존닷컴": "AMZN",
            "카디널 헬스": "CAH", "TSMC(ADR)": "TSM",
            "PROETF ULTRAPRO QQQ": "TQQQ", "INVESCO QQQ TRUST UNIT SER 1": "QQQ"
        }
        # ✅ 내 포트폴리오 데이터 가져오기
        df_portfolio = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
        # ✅ NaN 방지 (NaN -> "Unknown")
        df_portfolio["converted_ticker"] = df_portfolio["ticker"].map(ticker_mapping).fillna("Unknown")
        df_portfolio["evaluation_amount"] = df_portfolio["evaluation_amount"].fillna(0)
        # ✅ 변환된 Symbol을 사용하여 S&P 500 데이터와 매칭
        df_merged = df_portfolio.merge(df_sp500, on="converted_ticker", how="left")
        df_merged.loc[:, "Sector"] = df_merged["Sector"].fillna("Non-S&P 500")
        # ✅ 섹터별 평가금액 및 종목별 정보 수집
        sector_info = {}
        for sector, group in df_merged.groupby("Sector"):
            stocks = [{"ticker": row["converted_ticker"] if pd.notna(row["converted_ticker"]) else "Unknown",
                       "price": row["evaluation_amount"]} for _, row in group.iterrows()]
            sector_info[sector] = {
                "total_value": group["evaluation_amount"].sum(),
                "stocks": stocks
            }
        return jsonify(sector_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_exchange_rate_data", methods=["GET"])
def get_exchange_rate_data():
    """ USD/KRW 환율 데이터를 JSON 형식으로 반환하는 엔드포인트 """
    try:
        df = fdr.DataReader('USD/KRW', '2023')  # 최근 데이터 가져오기
        df = df[['Close']].reset_index()  # 날짜를 인덱스에서 컬럼으로 변환
        df.rename(columns={'Close': 'exchange_rate', 'index': 'date'}, inplace=True)
        # ✅ NaN 값 제거
        df = df.dropna(subset=['exchange_rate'])
        # ✅ 1월 1일 데이터 필터링하여 제거
        df = df[~df["date"].dt.strftime('%m-%d').eq("01-01")]
        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "rates": df["exchange_rate"].tolist()
        })
    except Exception as e:
        print("\n❌ ERROR in get_exchange_rate_data:", str(e))  # 오류 메시지 출력
        return jsonify({"error": str(e)}), 500

@app.route("/get_stock_detail_finnhub")
def get_stock_detail_finnhub():
    from datetime import datetime

    ticker = request.args.get("ticker", "").upper()
    print(f"🚀 요청 ticker={ticker}")

    try:
        price = get_quote(ticker)
        df = get_candle_data(ticker)
        if df is None or df.empty:
            return jsonify({"error": f"{ticker}의 시세 데이터를 가져올 수 없습니다."}), 400
        df = calculate_indicators(df)
        if df.empty:
            return jsonify({"error": f"{ticker}의 기술 지표를 계산할 수 없습니다."}), 400
        latest = df.iloc[-1]
        return jsonify({
            "ticker": ticker,
            "price": price,
            "rsi": round(latest["RSI"], 2),
            "golden_cross": latest["MA5"] > latest["MA20"],
            "chart_data": {
                "dates": df["date"].dt.strftime('%Y-%m-%d').tolist(),
                "close": df["close"].round(2).tolist(),
                "MA5": df["MA5"].round(2).tolist(),
                "MA20": df["MA20"].round(2).tolist()
            }
        })
    except Exception as e:
        print("❌ 서버 오류:", e)
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500

@app.route('/favicon.ico')
def favicon():
    return '', 204  # 빈 응답 반환

if __name__ == "__main__":
    # Flask 애플리케이션 실행
    app.run(debug=True)