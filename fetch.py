import json, time, gzip, hashlib
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "feeds"
CFG = ROOT / "feeds.json"
INDEX = ROOT / "index.html"

OUT.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (RSS-Proxy; +https://github.com)"
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
            if r.headers.get("Content-Encoding", "").lower() == "gzip":
                data = gzip.decompress(data)
            return data
        except Exception as e:
            last_exc = e
            print(f"[RETRY {i+1}] {url} -> {e}")
            time.sleep(1.5 * (i + 1))
    raise last_exc

def write_bytes(path: Path, data: bytes) -> bool:
    before = path.read_bytes() if path.exists() else None
    if before == data:
        return False
    path.write_bytes(data)
    return True

def placeholder_xml(name: str, src: str, err: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{name} (mirror error)</title>
    <link>{src}</link>
    <description>Failed to fetch source: {err}</description>
    <item>
      <title>Mirror unavailable</title>
      <link>{src}</link>
      <description><![CDATA[{err}]]></description>
      <pubDate>{time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())}</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

def build_index(rows):
    items = "\n".join(
        f'<li><a href="feeds/{row["file"]}" target="_blank" rel="noopener">'
        f'{row["name"]}</a> &nbsp;<code>feeds/{row["file"]}</code></li>'
        for row in rows
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>RSS Proxy</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<h1>RSS Proxy</h1>
<ol>
{items}
</ol>
<p>Generated at {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}</p>
</html>"""

def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    rows = []
    for row in cfg:
        name, src, file = row["name"], row["source"], row["file"]
        dest = OUT / file
        try:
            data = fetch(src)
            changed = write_bytes(dest, data)
            print(f"[{ 'UPDATED' if changed else 'NOCHANGE' }] {name} -> feeds/{file}")
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            data = placeholder_xml(name, src, str(e))
            write_bytes(dest, data)  # 一定写出占位，确保后续能提交
        rows.append({"name": name, "file": file})

    # index.html
    html = build_index(rows).encode("utf-8")
    write_bytes(INDEX, html)

if __name__ == "__main__":
    main()
