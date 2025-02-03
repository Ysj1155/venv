from flask import Flask, render_template, request, jsonify
import pandas as pd
import os, datetime
import utils

app = Flask(__name__)
DATA_FILE = "data/account_data.csv"

# 데이터 초기화 (account_data.csv 파일이 없으면 생성)
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=["ticker", "price", "quantity", "purchase_time"]).to_csv(DATA_FILE, index=False)

@app.route("/")
def index():
    """
    메인 페이지 렌더링
    account_data.csv에서 데이터를 불러와 웹 페이지에 표시
    """
    encoding = utils.detect_encoding(DATA_FILE)
    data = pd.read_csv(DATA_FILE, encoding=encoding)
    return render_template("index.html", stocks=data.to_dict(orient="records"))

@app.route("/get_pie_chart_data", methods=["GET"])
def get_pie_chart_data():
    """
    원형 차트 데이터를 반환하는 엔드포인트
    """
    encoding = utils.detect_encoding(DATA_FILE)
    data = pd.read_csv(DATA_FILE, encoding=encoding)

    # ✅ 컬럼명이 '매입단가'일 경우 'price'로 변경
    if "매입단가" in data.columns and "price" not in data.columns:
        data.rename(columns={"매입단가": "price"}, inplace=True)

    if "잔고수량" in data.columns and "quantity" not in data.columns:
        data.rename(columns={"잔고수량": "quantity"}, inplace=True)

    # ✅ 컬럼명이 '종목명'일 경우 'ticker'로 변경
    if "종목명" in data.columns and "ticker" not in data.columns:
        data.rename(columns={"종목명": "ticker"}, inplace=True)

    # NaN 값을 '예수금'으로 대체
    data["ticker"] = data["ticker"].fillna("예수금")

    # 포트폴리오 비율 계산
    total_value = (data["price"] * data["quantity"]).sum()
    if total_value == 0:
        return jsonify({"labels": [], "values": []})
    data["allocation"] = (data["price"] * data["quantity"]) / total_value * 100  # 퍼센트 계산

    return jsonify({
        "labels": data["ticker"].tolist(),
        "values": data["allocation"].tolist(),
        "total_value": total_value  # 원화 기준 총 금액 반환
    })


@app.route("/add_stock", methods=["POST"])
def add_stock():
    """
    새로운 주식 정보를 추가하는 엔드포인트
    사용자가 입력한 티커, 가격, 수량, 구매 날짜를 받아 저장
    """
    ticker = request.form["ticker"]
    price = float(request.form["price"])  # 매입단가
    quantity = int(request.form["quantity"])
    purchase_time = request.form["purchase_time"]

    # 현재 주가 가져오기 (yfinance 또는 다른 API 활용)
    current_price = get_current_price(ticker)
    current_value = current_price * quantity  # 평가금액

    # 티커 변환: "GOOGL; 알파벳 A" 형식 유지
    if ticker.isalpha():  # 미국 및 글로벌 주식
        full_name = get_stock_name(ticker)
    else:  # 한국 주식
        full_name = get_kr_stock_name(ticker)

    ticker = f"{ticker}; {full_name}"

    # 새로운 데이터를 데이터 파일에 추가
    new_data = pd.DataFrame([{
        "ticker": ticker,
        "purchase_price": price,
        "quantity": quantity,
        "purchase_time": purchase_time,
        "current_price": current_price,
        "current_value": current_value
    }])
    print("New Data to be Saved:", new_data)  # 콘솔에서 데이터 확인
    new_data.to_csv(DATA_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")

    return jsonify({"success": True, "message": "Stock added successfully!"})


if __name__ == "__main__":
    # Flask 애플리케이션 실행
    app.run(debug=True)
