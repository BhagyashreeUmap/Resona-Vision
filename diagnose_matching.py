
import csv
from collections import Counter
from pathlib import Path

from engine.cv_core import CFG, decode_image, normalize, match_images

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"
LABELS = DATASET / "labels.csv"

references = {}
rows = []

with LABELS.open("r", newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row["split"] != "dev":
            continue
        if row["photo_type"].lower() == "reference":
            references.setdefault(row["product"], DATASET / row["file"])
        else:
            rows.append(row)

configs = {
    "CURRENT": {**CFG, "ratio": 0.75},
    "RELAXED": {**CFG, "ratio": 0.85},
    "WIDER": {**CFG, "ratio": 0.90},
}

for config_name, cfg in configs.items():
    counts = Counter()
    print(f"\n=== {config_name} ===")
    print(f"{'Product':<8} {'Photo':<27} {'Inliers':>7} {'Good':>6} {'Ratio':>7} {'Status':>10}")
    print("-" * 72)

    for row in rows:
        photo = DATASET / row["file"]
        ref_path = references.get(row["product"])

        if not photo.exists() or not ref_path or not ref_path.exists():
            continue

        img = normalize(decode_image(photo.read_bytes()), cfg["norm_width"])
        ref = normalize(decode_image(ref_path.read_bytes()), cfg["norm_width"])
        result = match_images(img, ref, cfg)

        if (result["inliers"] >= cfg["match_good"]
                and result["ratio"] >= cfg["match_ratio"]):
            status = "MATCH"
        elif result["inliers"] >= cfg["match_weak"]:
            status = "WEAK"
        else:
            status = "NO_MATCH"

        counts[status] += 1
        print(
            f"{row['product']:<8} {photo.name:<27} "
            f"{result['inliers']:>7} {result['good']:>6} "
            f"{result['ratio']:>7.2f} {status:>10}"
        )

    print("SUMMARY:", dict(counts))
