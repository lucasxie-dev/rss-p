import json, time, gzip, io, hashlib
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "feeds"
CFG = ROOT / "feeds.json"
INDEX = ROOT / "index.html"

OUT.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (RSS-Proxy; +https://github.com/yourname/rss-proxy)"
TIMEOUT = 15
RETRIES = 3

def fetch(url: str) -> bytes:
    last_exc = None
    for i in range(RETRIES):
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.content
            # 解压 gzip
            if r.headers.get("Content-Encoding", "").lower() == "gzip":
                data = gzip.decompress(data)
            return data
        except Exception as e:
            last_exc = e
            time.sleep(1.5 * (i + 1))
    raise last_exc

def write_if_changed(path: Path, data: bytes) -> bool:
    if path.exists():
        if hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(data).digest():
            return False
    path.write_bytes(data)
    return True

def build_index(rows):
    # 简单的目录页，方便用户点击复制
    items = "\n".join(
        f'<li><a href="feeds/{row["file"]}" target="_blank" rel="noopener">{row["name"]}</a> '
        f'&nbsp; <code>feeds/{row["file"]}</code></li>'
        for row in rows
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>RSS Proxy</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:24px;line-height:1.6}}
code{{background:#f4f4f4;padding:2px 4px;border-radius:4px}}
</style>
<h1>RSS Proxy (GitHub Pages)</h1>
<p>Mirrored feeds for regions where originals are hard to access. Content is unmodified and for personal/educational use. Attribution preserved.</p>
<ol>
{items}
</ol>
<hr>
<p>Generated at {time.strftime("%Y-%m-%d %H:%M:%S %Z", time.gmtime())}</p>
</html>"""

def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    rows = []
    changed_any = False

    for row in cfg:
        name = row["name"]
        src = row["source"]
        file = row["file"]
        dest = OUT / file
        try:
            data = fetch(src)
            if write_if_changed(dest, data):
                print(f"[UPDATED] {name} -> feeds/{file}")
                changed_any = True
            else:
                print(f"[NOCHANGE] {name}")
            rows.append({"name": name, "file": file})
        except Exception as e:
            print(f"[ERROR] {name}: {e}")

    # 重建 index.html
    index_html = build_index(rows)
    if write_if_changed(INDEX, index_html.encode("utf-8")):
        changed_any = True

    if changed_any:
        print("Done: changes committed in workflow.")
    else:
        print("Done: nothing changed.")

if __name__ == "__main__":
    main()
