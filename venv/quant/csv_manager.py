import os
import pandas as pd
from datetime import datetime

# 데이터 저장 경로
DATA_DIR = "data"
MERGED_FILE = os.path.join(DATA_DIR, "merged_data.csv")

def load_template_format(template_file):
    """ 기준이 되는 템플릿 CSV 파일의 컬럼명을 가져옴 """
    template_df = pd.read_csv(template_file, nrows=5)  # 일부만 읽어서 형식 확인
    expected_columns = list(template_df.columns)
    return expected_columns

def convert_and_merge_csv(new_csv_path, template_file):
    """
    새로운 CSV 데이터를 기준 형식에 맞춰 변환 후 기존 데이터와 병합하는 함수
    """
    if not os.path.exists(new_csv_path):
        print(f"❌ 파일을 찾을 수 없음: {new_csv_path}")
        return

    # 날짜 추출 (예: "01_30.csv" → "2025-01-30")
    file_name = os.path.basename(new_csv_path)
    date_str = file_name.replace(".csv", "").replace("_", "-")
    formatted_date = f"2025-{date_str}"  # 연도는 2025년으로 고정

    # 템플릿 기준 컬럼 로드
    expected_columns = load_template_format(template_file)

    # 새로운 데이터 불러오기
    new_data = pd.read_csv(new_csv_path)

    # 기준 컬럼을 맞추기 위해 부족한 컬럼은 NaN으로 추가
    for col in expected_columns:
        if col not in new_data.columns:
            new_data[col] = None  # 없는 컬럼은 NaN 값으로 채움

    # 불필요한 컬럼 제거 (템플릿에 없는 컬럼은 제거)
    new_data = new_data[expected_columns]

    # 날짜 컬럼 추가
    new_data["Date"] = formatted_date

    # 기존 병합된 데이터 로드 (있으면)
    if os.path.exists(MERGED_FILE):
        merged_data = pd.read_csv(MERGED_FILE)
        merged_data = pd.concat([merged_data, new_data], ignore_index=True)
    else:
        merged_data = new_data

    # 중복 제거
    merged_data.drop_duplicates(inplace=True)

    # 최신 데이터 저장
    merged_data.to_csv(MERGED_FILE, index=False, encoding="utf-8-sig")
    print(f"✅ 데이터 병합 완료: {MERGED_FILE}")

# 실행 예제
if __name__ == "__main__":
    template_file = os.path.join(DATA_DIR, "02_03.csv")  # 최신 기준 템플릿 파일

    # 예제: 1월 30일 데이터 추가
    new_csv_file = os.path.join(DATA_DIR, "01_30.csv")

    convert_and_merge_csv(new_csv_file, template_file)
