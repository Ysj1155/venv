import os, csv
import pandas as pd
import matplotlib.pyplot as plt

CSV = "results.csv"
OUT = "plots"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(CSV)

# 러닝 이름: policy + note (있으면)
def run_name(row):
    note = str(row.get("note") or "").strip()
    return f'{row["policy"]} ({note})' if note else str(row["policy"])

df["run"] = df.apply(run_name, axis=1)

# 1) WAF 막대그래프
ax = df.plot(kind="bar", x="run", y="WAF", legend=False, figsize=(10,5), title="WAF by run")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "waf_by_run.png"))
plt.close()

# 2) GC count 막대그래프
ax = df.plot(kind="bar", x="run", y="GC_count", legend=False, figsize=(10,5), title="GC count by run")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "gc_by_run.png"))
plt.close()

# 3) GC time p99 막대그래프
if "gc_time_p99_ms" in df.columns:
    ax = df.plot(kind="bar", x="run", y="gc_time_p99_ms", legend=False, figsize=(10,5), title="GC time p99 (ms) by run")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "gc_p99_by_run.png"))
    plt.close()

print("[OK] Saved plots to:", OUT)
