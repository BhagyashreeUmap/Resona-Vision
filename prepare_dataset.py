
from pathlib import Path
import csv
import random
import re
import shutil

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "dataset" / "raw"
DEV = ROOT / "dataset" / "dev"
TEST = ROOT / "dataset" / "test"
CSV_PATH = ROOT / "dataset" / "labels.csv"

random.seed(42)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

files = [
    p for p in RAW.rglob("*")
    if p.is_file() and p.suffix.lower() in IMAGE_EXTS
]

def product_id(path):
    match = re.match(r"^(P\d+)_", path.stem, re.IGNORECASE)
    return match.group(1).upper() if match else None

def photo_type(path):
    name = path.stem.lower()
    if "reference" in name:
        return "reference"
    if "damage" in name or "damaged" in name:
        return "damage"
    if "blur" in name:
        return "blur"
    if "black" in name:
        return "dark"
    if "far" in name:
        return "far"
    if "angle" in name:
        return "angle"
    if "clear" in name:
        return "clear"
    return "unknown"

if len(files) != 89:
    raise SystemExit(f"Expected 89 images; found {len(files)}.")

if any(product_id(p) is None for p in files):
    raise SystemExit("Some filenames do not start with P<number>_. Check filenames.")

# References stay in dev. Other photos are split per product and photo type.
rows = []
for product in sorted({product_id(p) for p in files},
                      key=lambda x: int(x[1:])):
    product_files = [p for p in files if product_id(p) == product]

    for p in product_files:
        kind = photo_type(p)
        split = "dev" if kind == "reference" else None
        rows.append({
            "file": p.relative_to(RAW).as_posix(),
            "product": product,
            "photo_type": kind,
            "quality": "unknown",
            "damage": "unknown",
            "split": split,
        })

    groups = {}
    for row in rows:
        if row["product"] == product and row["split"] is None:
            groups.setdefault(row["photo_type"], []).append(row)

    for group in groups.values():
        random.shuffle(group)
        if len(group) == 1:
            group[0]["split"] = "dev"
        else:
            test_count = max(1, round(len(group) * 0.4))
            for i, row in enumerate(group):
                row["split"] = "test" if i < test_count else "dev"

# Refuse to overwrite existing split folders.
for folder in (DEV, TEST):
    if any(folder.iterdir()) if folder.exists() else False:
        raise SystemExit(
            f"{folder} is not empty. Stop to avoid overwriting existing work."
        )

DEV.mkdir(parents=True, exist_ok=True)
TEST.mkdir(parents=True, exist_ok=True)

for row in rows:
    source = RAW / row["file"]
    target_folder = DEV if row["split"] == "dev" else TEST
    target = target_folder / source.name

    # Prevent filename collisions within a split.
    if target.exists():
        target = target_folder / f"{row['product']}_{source.name}"

    shutil.copy2(source, target)
    row["file"] = f"{row['split']}/{target.name}"

with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["file", "product", "photo_type", "quality", "damage", "split"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Images processed: {len(rows)}")
print(f"Dev images: {sum(r['split'] == 'dev' for r in rows)}")
print(f"Test images: {sum(r['split'] == 'test' for r in rows)}")
print(f"Manifest: {CSV_PATH}")
print("Original raw images were not modified.")
