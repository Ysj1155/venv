from flask import Flask, render_template, request, jsonify
import FinanceDataReader as fdr
import pandas as pd
import utils, csv_manager

app = Flask(__name__)

@app.route("/")
def index():
    """ 메인 페이지 렌더링 """
    data = utils.load_data()
    return render_template("index.html", stocks=data.to_dict(orient="records"))


def get_usd_krw_exchange_rate():
    """USD/KRW 환율 데이터를 가져와 JSON 형태로 반환하는 함수"""
    df = fdr.DataReader('USD/KRW', '2020')  # 2020년부터 현재까지 데이터 가져오기
    df = df[['Close']].reset_index()  # 'Date' 열 포함
    df.rename(columns={'Close': 'exchange_rate', 'Date': 'date'}, inplace=True)  # Date 컬럼 유지
    return df


@app.route("/get_exchange_rate_data", methods=["GET"])
def get_exchange_rate_data():
    """USD/KRW 환율 데이터를 JSON 형식으로 반환하는 엔드포인트"""
    try:
        df = fdr.DataReader('USD/KRW', '2022-01-01')  # 최근 데이터 가져오기
        df = df[['Adj Close']].reset_index()  # 인덱스를 'date' 컬럼으로 변환
        df.rename(columns={'Adj Close': 'exchange_rate', 'index': 'date'}, inplace=True)

        # ✅ 1월 1일 데이터 필터링하여 제거
        df = df[~df["date"].dt.strftime('%m-%d').eq("01-01")]

        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "rates": df["exchange_rate"].tolist()
        })
    except Exception as e:
        print("\n❌ ERROR in get_exchange_rate_data:", str(e))  # 오류 메시지 출력
        return jsonify({"error": str(e)}), 500




@app.route("/get_pie_chart_data", methods=["GET"])
def get_pie_chart_data():
    """ 최신 날짜 기준으로 원형 차트 데이터를 반환하는 엔드포인트 """
    data = utils.get_pie_chart_data()
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
    """ 날짜별 총 평가금액 데이터를 반환하는 엔드포인트 """
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


watchlist = []  # 관심 종목 리스트
@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    """관심 종목 리스트에 종목 추가"""
    data = request.get_json()
    ticker = data.get("ticker")

    if ticker and ticker not in watchlist:
        watchlist.append(ticker)
        return jsonify({"message": "Ticker added", "watchlist": watchlist})
    else:
        return jsonify({"error": "Invalid ticker or already exists"}), 400

@app.route("/get_watchlist", methods=["GET"])
def get_watchlist():
    """현재 저장된 관심 종목 리스트 반환"""
    return jsonify({"watchlist": watchlist})


@app.route("/get_graph_data", methods=["GET"])
def get_graph_data():
    """전체 포트폴리오 수익률 데이터를 JSON 형식으로 반환"""
    try:
        # 가상의 수익률 데이터 생성 (데이터가 없는 경우를 대비)
        data = pd.DataFrame({
            "date": pd.date_range(start="2024-01-01", periods=30, freq="D"),
            "profit": [i * 0.5 for i in range(30)]  # 0.5%씩 증가하는 수익률 예제
        })

        return jsonify({
            "dates": data["date"].astype(str).tolist(),
            "profits": data["profit"].tolist()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/favicon.ico')
def favicon():
    return '', 204  # 빈 응답 반환


if __name__ == "__main__":
    # Flask 애플리케이션 실행
    app.run(debug=True)
