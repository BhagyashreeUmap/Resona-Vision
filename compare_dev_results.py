import csv
from collections import Counter

path = "dataset/dev_results.csv"
with open(path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

quality = Counter()
damage = Counter()
product = Counter()

for r in rows:
    if r["expected_quality"] in ("ok", "bad"):
        quality[(r["expected_quality"], r["predicted_quality"])] += 1

    if r["expected_damage"] in ("none", "damaged"):
        damage[(r["expected_damage"], r["predicted_damage"])] += 1

    product[(r["product"], r["product_status"])] += 1

print("QUALITY: expected -> predicted")
for key, count in sorted(quality.items()):
    print(key, count)

print("\nDAMAGE: expected -> predicted")
for key, count in sorted(damage.items()):
    print(key, count)

print("\nEXAMPLES: labeled damage but engine says UNKNOWN")
for r in rows:
    if r["expected_damage"] in ("none", "damaged") and r["predicted_damage"] == "UNKNOWN":
        print(r["file"], "| expected:", r["expected_damage"],
              "| product:", r["product_status"])
