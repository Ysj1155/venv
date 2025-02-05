import os
import pandas as pd

# 데이터 경로
DATA_DIR = "data"
MERGED_FILE = os.path.join(DATA_DIR, "merged_data.csv")

# 컬럼 매핑 (한글 → 영어)
COLUMN_MAP = {
    "구분": "type",
    "계좌번호": "account_number",
    "종목명": "ticker",
    "평가손익": "profit_loss",
    "손익률": "profit_rate",
    "잔고수량": "quantity",
    "매입단가": "purchase_price",
    "매입금액": "purchase_amount",
    "평가금액": "evaluation_amount",
    "평가비중": "evaluation_ratio",
    "날짜": "date"
}


def preprocess_csv(file_path):
    """ CSV 파일을 정리하고 컬럼을 변환하는 함수 """
    if not os.path.exists(file_path):
        print(f"❌ 파일 없음: {file_path}")
        return None

    data = pd.read_csv(file_path, encoding="utf-8-sig")
    data = data[list(COLUMN_MAP.keys())]  # 필요한 컬럼 선택
    data.rename(columns=COLUMN_MAP, inplace=True)  # 컬럼명 변환
    # ✅ "type"이 "외화예수금" 또는 "예수금"이면 "ticker" 값을 해당 이름으로 설정
    data.loc[data["type"] == "외화예수금", "ticker"] = "외화예수금"
    data.loc[data["type"] == "예수금", "ticker"] = "예수금"
    return data


def merge_csv(new_csv_path):
    """ 새로운 CSV 데이터를 기존 데이터와 병합 """
    new_data = preprocess_csv(new_csv_path)
    if new_data is None:
        return

    if os.path.exists(MERGED_FILE):
        merged_data = pd.read_csv(MERGED_FILE, encoding="utf-8-sig")
        merged_data = pd.concat([merged_data, new_data], ignore_index=True)
    else:
        merged_data = new_data

    merged_data.drop_duplicates(inplace=True)
    merged_data.to_csv(MERGED_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ 데이터 병합 완료: {MERGED_FILE}")


def add_stock_to_csv(ticker, price, quantity, purchase_time):
    """ 주식을 CSV 파일에 추가하는 함수 """
    new_data = pd.DataFrame([{
        "ticker": ticker,
        "purchase_price": price,
        "quantity": quantity,
        "purchase_time": purchase_time,
        "evaluation_amount": price * quantity
    }])

    if os.path.exists(MERGED_FILE):
        new_data.to_csv(MERGED_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        new_data.to_csv(MERGED_FILE, index=False, encoding="utf-8-sig")


def get_latest_data():
    """ 최신 데이터를 불러오는 함수 """
    if not os.path.exists(MERGED_FILE):
        return pd.DataFrame()

    return pd.read_csv(MERGED_FILE, encoding="utf-8-sig")

def get_total_value_by_date():
    """ 날짜별 평가금액 총합을 계산하는 함수 """
    if not os.path.exists(MERGED_FILE):
        return pd.DataFrame()

    data = pd.read_csv(MERGED_FILE, encoding="utf-8-sig")
    if "date" not in data.columns or "evaluation_amount" not in data.columns:
        return pd.DataFrame()

    data["date"] = pd.to_datetime(data["date"])  # 날짜 변환
    data["evaluation_amount"] = data["evaluation_amount"].astype(str).str.replace(",", "").astype(float)

    total_value_by_date = data.groupby("date")["evaluation_amount"].sum().reset_index()
    return total_value_by_date