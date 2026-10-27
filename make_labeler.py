from pathlib import Path
import csv
import html
import json
from urllib.parse import quote

root = Path(__file__).resolve().parent
dataset = root / "dataset"
csv_path = dataset / "labels.csv"
output = dataset / "photo_gallery.html"

rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig", newline="")))
cards = []

for i, row in enumerate(rows):
    rel = Path(row["file"])
    image = dataset / rel
    if not image.exists():
        print("Missing image:", image)
        continue

    src = quote(rel.as_posix(), safe="/")
    name = html.escape(image.name)
    product = html.escape(row["product"])
    quality = row.get("quality", "unknown")
    damage = row.get("damage", "unknown")

    def options(values, selected):
        return "".join(
            f'<option value="{v}" {"selected" if v == selected else ""}>{v}</option>'
            for v in values
        )

    cards.append(f"""
    <article class="card" data-index="{i}">
      <img src="{src}" loading="lazy" alt="{name}">
      <h3>{name}</h3>
      <p>Product: {product} | Split: {html.escape(row["split"])}</p>
      <label>Quality
        <select class="quality">
          {options(["unknown", "ok", "bad"], quality)}
        </select>
      </label>
      <label>Damage
        <select class="damage">
          {options(["unknown", "none", "damaged"], damage)}
        </select>
      </label>
    </article>""")

data = json.dumps(rows).replace("</", "<\\/")

page = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resona Vision Labeler</title>
<style>
body{font:16px Arial;margin:20px;background:#f5f1e9;color:#222}
header{position:sticky;top:0;background:#f5f1e9;padding:12px;z-index:2}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.card{background:white;border-radius:10px;padding:12px;overflow-wrap:anywhere}
img{width:100%;height:210px;object-fit:contain;background:#eee}
label{display:block;margin:12px 0;font-weight:bold}
select,button{width:100%;padding:10px;margin-top:5px;font-size:16px}
button{cursor:pointer;background:#8d352d;color:white;border:0;border-radius:6px}
</style></head><body>
<header><h1>Resona Vision — Label Photos</h1>
<p>For each image, label photo usability and visible product damage.</p>
<p id="count"></p>
<button onclick="saveLabels()">Save labels to CSV</button>
<p id="status">Changes are not saved until you click Save.</p></header>
<div class="grid">""" + "\n".join(cards) + """
</div><script>
const rows = """ + data + """;
document.getElementById('count').textContent = rows.length + ' images';
function csvEscape(v){return '"' + String(v ?? '').replace(/"/g,'""') + '"';}
function saveLabels(){
  document.querySelectorAll('.card').forEach(card=>{
    const r=rows[Number(card.dataset.index)];
    r.quality=card.querySelector('.quality').value;
    r.damage=card.querySelector('.damage').value;
  });
  const cols=['file','product','photo_type','quality','damage','split'];
  const csv=[cols.join(','),...rows.map(r=>cols.map(c=>csvEscape(r[c])).join(','))].join('\\r\\n');
  const blob=new Blob(['\\ufeff'+csv],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='labels.csv';a.click();
  URL.revokeObjectURL(a.href);
  document.getElementById('status').textContent=
    'CSV downloaded. Replace dataset/labels.csv with the downloaded file.';
}
</script></body></html>"""

output.write_text(page, encoding="utf-8")
print("Labeling gallery created:", output)
print("Images:", len(cards))
