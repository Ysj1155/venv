from flask import Flask, render_template, request, jsonify
from utils.finance_utils import get_current_price
import pandas as pd
import os

app = Flask(__name__)
DATA_FILE = "data/account_data.csv"

# 데이터 초기화
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=["ticker", "price", "quantity", "purchase_time"]).to_csv(DATA_FILE, index=False)

@app.route("/")
def index():
    # 데이터 로드 및 수익률 계산
    data = pd.read_csv(DATA_FILE)
    data["current_price"] = data["ticker"].apply(get_current_price)
    data["profit_percent"] = ((data["current_price"] - data["price"]) / data["price"] * 100).round(2)
    return render_template("index.html", stocks=data.to_dict(orient="records"))

@app.route("/add_stock", methods=["POST"])
def add_stock():
    # 입력 데이터를 저장
    ticker = request.form["ticker"]
    price = float(request.form["price"])
    quantity = int(request.form["quantity"])
    purchase_time = request.form["purchase_time"]

    # CSV 파일에 추가
    new_data = pd.DataFrame([{"ticker": ticker, "price": price, "quantity": quantity, "purchase_time": purchase_time}])
    new_data.to_csv(DATA_FILE, mode="a", header=False, index=False)

    return jsonify({"success": True, "message": "Stock added successfully!"})

@app.route("/get_graph_data", methods=["GET"])
def get_graph_data():
    data = pd.read_csv(DATA_FILE)
    data["current_value"] = data.apply(
        lambda row: row["quantity"] * get_current_price(row["ticker"]), axis=1
    )
    cumulative_value = data["current_value"].cumsum().tolist()
    return jsonify({"dates": data["purchase_time"].tolist(), "values": cumulative_value})

if __name__ == "__main__":
    app.run(debug=True)
