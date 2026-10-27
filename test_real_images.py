
import csv
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
from cv_core import analyze, decode_image, normalize, check_product, CFG

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"

with (DATASET / "labels.csv").open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

dev_rows = [r for r in rows if r["split"] == "dev"]

# Collect every dev reference for each product.
references = {}
for r in dev_rows:
    if r["photo_type"].lower() == "reference":
        references.setdefault(r["product"], []).append(DATASET / r["file"])

def read_image(path):
    return path.read_bytes() if path and path.is_file() else None

results = []

for r in dev_rows:
    photo_path = DATASET / r["file"]

    try:
        photo_bytes = read_image(photo_path)
        if not photo_bytes:
            continue

        # Keep normal analysis, then compare all references to find the strongest match.
        best = None
        photo = normalize(
            decode_image(photo_bytes), CFG["norm_width"]
        )

        for ref_path in references.get(r["product"], []):
            ref_bytes = read_image(ref_path)
            if not ref_bytes:
                continue

            ref = normalize(decode_image(ref_bytes), CFG["norm_width"])
            product_result, H = check_product(photo, ref, CFG)

            candidate = (product_result, H, ref_bytes)
            if best is None:
                best = candidate
            else:
                old_result, old_H, _ = best
                rank = {"MATCH": 2, "WEAK": 1, "NO_MATCH": 0}
                if (
                    rank[product_result["status"]] > rank[old_result["status"]]
                    or (
                        product_result["status"] == old_result["status"]
                        and product_result["inliers"] > old_result["inliers"]
                    )
                ):
                    best = candidate

        if best:
            _, _, ref_bytes = best
        else:
            ref_bytes = None

        result, _ = analyze(
            photo_bytes,
            ref_bytes,
            [],
            lambda item: b"",
        )

        results.append({
            "file": r["file"],
            "product": r["product"],
            "expected_quality": r["quality"],
            "predicted_quality": "ok" if result["quality"]["ok"] else "bad",
            "expected_damage": r["damage"],
            "predicted_damage": result["damage"]["level"],
            "product_status": result["product"]["status"],
            "evidence_score": result["evidence_score"],
            "reason_codes": "|".join(result["reason_codes"]),
        })

    except Exception as e:
        print("ERROR:", r["file"], repr(e))

out = DATASET / "dev_results.csv"
if results:
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

print("Dev images:", len(dev_rows))
print("Analyzed:", len(results))
print("Product statuses:", Counter(x["product_status"] for x in results))
print("Damage levels:", Counter(x["predicted_damage"] for x in results))
print("Results saved:", out)
