from flask import Flask, render_template, request, jsonify
from forex_python.converter import CurrencyRates
import pandas as pd
import os, datetime

app = Flask(__name__)
DATA_FILE = "data/account_data.csv"

# 데이터 초기화
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=["ticker", "price", "quantity", "purchase_time"]).to_csv(DATA_FILE, index=False)

@app.route("/")
def index():
    data = pd.read_csv(DATA_FILE)
    return render_template("index.html", stocks=data.to_dict(orient="records"))

@app.route("/add_stock", methods=["POST"])
def add_stock():
    ticker = request.form["ticker"]
    price = float(request.form["price"])  # float로 변환
    quantity = int(request.form["quantity"])
    purchase_time = request.form["purchase_time"]

    new_data = pd.DataFrame([{"ticker": ticker, "price": price, "quantity": quantity, "purchase_time": purchase_time}])
    new_data.to_csv(DATA_FILE, mode="a", header=False, index=False)

    return jsonify({"success": True, "message": "Stock added successfully!"})

@app.route("/get_graph_data", methods=["GET"])
def get_graph_data():
    data = pd.read_csv(DATA_FILE)
    data["total_value"] = data["price"] * data["quantity"]
    cumulative_profit = data["total_value"].cumsum().tolist()
    return jsonify({"dates": data["purchase_time"].tolist(), "profits": cumulative_profit})

@app.route("/get_exchange_rate", methods=["GET"])
def get_exchange_rate():
    currency_rates = CurrencyRates()
    base_currency = "USD"
    target_currency = "KRW"
    rate = currency_rates.get_rate(base_currency, target_currency)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"timestamp": timestamp, "rate": rate})

@app.route("/get_exchange_rate_data", methods=["GET"])
def get_exchange_rate_data():
    """
    환율 데이터를 반환하는 엔드포인트
    """
    currency_pair = "USD/KRW"  # 예: USD/KRW
    file_path = f"data/{currency_pair.replace('/', '_')}.csv"

    if not os.path.exists(file_path):
        return jsonify({"error": "Exchange rate data not found"}), 404

    # CSV 파일 로드
    data = pd.read_csv(file_path)
    return jsonify({
        "dates": data["Date"].tolist(),
        "rates": data["Close"].tolist()
    })

if __name__ == "__main__":
    app.run(debug=True)
