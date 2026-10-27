import csv
from pathlib import Path
from collections import Counter

root = Path.cwd()
dataset = root / "dataset"
rows = list(csv.DictReader((dataset / "labels.csv").open(encoding="utf-8-sig")))

missing = [r["file"] for r in rows if not (dataset / r["file"]).is_file()]
duplicates = len(rows) - len(set(r["file"] for r in rows))

print("CSV rows:", len(rows))
print("Missing image files:", len(missing))
print("Duplicate CSV entries:", duplicates)
print("Split counts:", Counter(r["split"] for r in rows))
print("Quality labels:", Counter(r["quality"] for r in rows))
print("Damage labels:", Counter(r["damage"] for r in rows))

if len(rows) == 89 and not missing and duplicates == 0:
    print("\nPASS: Dataset files and CSV match.")
else:
    print("\nCHECK REQUIRED.")
    if missing:
        print("Missing:", missing)
