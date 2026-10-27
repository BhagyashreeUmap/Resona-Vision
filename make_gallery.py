import csv
import html
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parent
dataset = root / "dataset"
csv_path = dataset / "labels.csv"
output = dataset / "photo_gallery.html"

cards = []
with csv_path.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        rel = Path(row["file"])
        image_path = dataset / rel
        if not image_path.is_file():
            print("MISSING:", image_path)
            continue

        src = quote(rel.as_posix(), safe="/")
        name = html.escape(image_path.name)
        product = html.escape(row["product"])
        split = html.escape(row["split"])
        kind = html.escape(row["photo_type"])

        cards.append(f"""
        <article>
          <img src="{src}" loading="lazy" alt="{name}">
          <p><b>{name}</b></p>
          <p>{product} | {kind} | {split}</p>
        </article>""")

page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resona Vision — Photo Gallery</title>
<style>
body{font:16px Arial,sans-serif;margin:24px;background:#f5f1e9;color:#252525}
h1{margin-bottom:6px} .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
article{background:white;padding:12px;border-radius:10px;overflow-wrap:anywhere}
img{width:100%;height:220px;object-fit:contain;background:#eee}
p{margin:8px 0}
</style>
</head>
<body>
<h1>Resona Vision — Photo Gallery</h1>
<p>Generated from dataset/labels.csv. Images shown: """ + str(len(cards)) + """</p>
<div class="grid">""" + "\n".join(cards) + """
</div></body></html>"""

output.write_text(page, encoding="utf-8")
print(f"Gallery updated: {output}")
print(f"Images included: {len(cards)}")
