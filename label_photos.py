
from pathlib import Path
import csv
import html
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

ROOT = Path(r"D:\Resona-Vision")
SOURCE = Path(r"D:\Resona_images")
DATASET = ROOT / "dataset"
LABELS = DATASET / "labels.csv"
DATASET.mkdir(exist_ok=True)

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
photos = sorted(
    [
        p for p in SOURCE.iterdir()
        if p.is_file() and p.suffix.lower() in EXTS
    ],
    key=lambda p: p.name.lower()
)

print(f"Photos loaded: {len(photos)}")

fields = ["file", "product", "quality", "damage", "split"]
saved = {}
if LABELS.exists():
    with LABELS.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            saved[row["file"]] = row

def page():
    cards = []
    for p in photos:
        row = saved.get(p.name, {})
        filename = html.escape(p.name)
        image_url = "/" + p.relative_to(SOURCE).as_posix()
        product = html.escape(row.get("product", ""))
        quality = row.get("quality", "")
        damage = row.get("damage", "")
        split = row.get("split", "")
        options = lambda choices, current: "".join(
            f'<option value="{v}" {"selected" if v == current else ""}>{label}</option>'
            for v, label in choices
        )
        cards.append(f"""
        <section class="card">
          <img src="{html.escape(image_url, quote=True)}" loading="lazy">
          <b>{filename}</b>
          <label>Object ID
            <select name="product" data-file="{filename}">
              {options([("", "-- choose --")] +
                [(f"P{i}", f"P{i}") for i in range(1,14)], product)}
            </select>
          </label>
          <label>Quality
            <select name="quality" data-file="{filename}">
              {options([("", "-- choose --"), ("ok","Clear enough"),
                        ("bad","Blurry / too dark / glare")], quality)}
            </select>
          </label>
          <label>Damage
            <select name="damage" data-file="{filename}">
              {options([("", "-- choose --"), ("none","No visible damage"),
                        ("damaged","Visible damage"),
                        ("unknown","Unclear / cannot tell")], damage)}
            </select>
          </label>
          <label>Split
            <select name="split" data-file="{filename}">
              {options([("", "-- choose --"), ("dev","Development"),
                        ("test","Test")], split)}
            </select>
          </label>
        </section>""")

    return """<!doctype html><html><head><meta charset="utf-8">
    <title>Resona Vision Labeler</title>
    <style>
    body{font-family:Arial;margin:20px;background:#f6f6f6}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
    .card{background:white;padding:12px;border:1px solid #ddd;border-radius:8px}
    img{width:100%;height:190px;object-fit:contain;background:#eee}
    label{display:block;margin-top:9px;font-size:14px}
    select{width:100%;padding:7px;margin-top:3px}
    button{padding:12px 20px;margin:12px 0;cursor:pointer}
    </style></head><body>
    <h2>Resona Vision — Label Photos</h2>
    <p>Choose the correct object and labels for each photo. Save regularly.</p>
    <button onclick="save()">Save labels.csv</button>
    <span id="status"></span>
    <div class="grid">""" + "".join(cards) + """
    </div><button onclick="save()">Save labels.csv</button>
    <script>
    async function save(){
      const rows=[...document.querySelectorAll('select')];
      const data={};
      rows.forEach(s=>{
        const f=s.dataset.file;
        if(!data[f]) data[f]={file:f,product:'',quality:'',damage:'',split:''};
        data[f][s.name]=s.value;
      });
      const r=await fetch('/save',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(Object.values(data))});
      document.getElementById('status').textContent=
        r.ok?'Saved successfully':'Save failed — try again';
    }
    </script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/save"):
            self.send_error(405)
        else:
            relative = path.lstrip("/")
            target = (SOURCE / relative).resolve()
            if not target.is_relative_to(SOURCE.resolve()) or not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", {
                ".jpg":"image/jpeg", ".jpeg":"image/jpeg",
                ".png":"image/png", ".webp":"image/webp",
                ".bmp":"image/bmp"
            }.get(target.suffix.lower(), "application/octet-stream"))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            rows = json.loads(self.rfile.read(length))
            with LABELS.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows({k: r.get(k, "") for k in fields} for r in rows)
            body = b"Saved"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))

server = HTTPServer(("127.0.0.1", 8765), Handler)
print("Labeler: http://127.0.0.1:8765")
print("Close this terminal or press Ctrl+C to stop.")
webbrowser.open("http://127.0.0.1:8765")
server.serve_forever()
