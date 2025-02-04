from flask import Flask, render_template, request, jsonify
import pandas as pd
import utils, csv_manager

app = Flask(__name__)

@app.route("/")
def index():
    """ 메인 페이지 렌더링 """
    data = utils.load_data()
    return render_template("index.html", stocks=data.to_dict(orient="records"))

@app.route("/get_pie_chart_data", methods=["GET"])
def get_pie_chart_data():
    """ 최신 날짜 기준으로 원형 차트 데이터를 반환하는 엔드포인트 """
    data = utils.load_data()
    return jsonify(data)

    # 최신 날짜 필터링
    data["Date"] = pd.to_datetime(data["Date"])  # 날짜 데이터 변환
    latest_date = data["Date"].max()  # 가장 최신 날짜 찾기
    latest_data = data[data["Date"] == latest_date]  # 최신 날짜의 데이터만 선택

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


@app.route("/get_total_value_data", methods=["GET"])
def get_total_value_data():
    """
    날짜별 총 평가금액 데이터를 반환하는 엔드포인트
    """
    encoding = utils.detect_encoding(DATA_FILE)
    data = pd.read_csv(DATA_FILE, encoding=encoding)

    # ✅ "Date" 컬럼이 없을 경우 오류 반환
    if "Date" not in data.columns or "평가금액" not in data.columns:
        return jsonify({"error": "CSV 파일에 'Date' 또는 '평가금액' 컬럼이 없습니다.", "columns": data.columns.tolist()}), 400

    # ✅ "Date" 컬럼을 날짜 형식으로 변환
    data["Date"] = pd.to_datetime(data["Date"])

    # ✅ "평가금액"을 숫자로 변환 (쉼표 제거 후 변환)
    data["평가금액"] = data["평가금액"].astype(str).str.replace(",", "").astype(float)

    # ✅ 날짜별 총 평가금액 계산
    total_value_by_date = data.groupby("Date")["평가금액"].sum().reset_index()

    # ✅ JSON 응답 형식으로 변환
    return jsonify({
        "dates": total_value_by_date["Date"].astype(str).tolist(),
        "total_values": total_value_by_date["평가금액"].tolist()
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
