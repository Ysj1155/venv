import pandas as pd
from db import conn, cursor  # 또는 from db import conn, cursor

df = pd.read_csv("data/account_value.csv", encoding="utf-8-sig")

for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO account_value (date, total_value)
        VALUES (%s, %s)
    """, (
        row["date"],
        int(float(str(row["total_value"]).replace(",", "")))
    ))

conn.commit()
print("✅ account_value 데이터 마이그레이션 완료")
