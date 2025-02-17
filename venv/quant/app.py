from flask import Flask, render_template, jsonify
import FinanceDataReader as fdr
import pandas as pd
import requests
import csv_manager  # ✅ CSV 데이터 처리를 `csv_manager.py`에서 가져옴

app = Flask(__name__)

# ✅ 서버 시작 시 CSV 데이터 최신화
csv_manager.process_account_value()
csv_manager.process_portfolio_data()

@app.route("/")
def index():
    """ 메인 페이지 렌더링 """
    try:
        portfolio_data = pd.read_csv(csv_manager.PORTFOLIO_FILE, encoding="utf-8-sig")
    except Exception as e:
        print(f"❌ Error loading portfolio data: {e}")
        portfolio_data = pd.DataFrame()  # 빈 DataFrame 반환

    return render_template("index.html", stocks=portfolio_data.to_dict(orient="records"))


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

@app.route("/get_account_value_data", methods=["GET"])
@app.route("/get_account_value_data", methods=["GET"])
def get_account_value_data():
    """ 날짜별 총 평가금액 및 수익률 데이터를 반환하는 엔드포인트 """
    try:
        df = pd.read_csv(csv_manager.ACCOUNT_VALUE_FILE, encoding="utf-8-sig")

        # ✅ 필수 컬럼 확인
        if "date" not in df.columns or "total_value" not in df.columns:
            return jsonify({"error": "CSV 파일에 'date' 또는 'total_value' 컬럼이 없습니다."}), 400

        # ✅ 최초 평가금액 설정 (첫 번째 날짜의 평가금액)
        initial_value = df["total_value"].iloc[0]

        # ✅ 총 평가금액 변화율(%) 계산
        df["profit"] = ((df["total_value"] - initial_value) / initial_value) * 100  # 최초 평가금액 대비 변화율(%) 계산

        return jsonify({
            "dates": df["date"].astype(str).tolist(),
            "total_values": df["total_value"].tolist(),  # 총 평가금액
            "profits": df["profit"].tolist()  # 계좌 수익률 (%)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

@app.route('/favicon.ico')
def favicon():
    return '', 204  # 빈 응답 반환


if __name__ == "__main__":
    # Flask 애플리케이션 실행
    app.run(debug=True)
