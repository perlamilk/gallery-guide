"""Downloads each Wadsworth on-view work's picture once (one at a time, 2 s apart), at most 420 px.
    python3 tools/fetch_wadsworth_images.py onview.jsonl images-folder/
Runs alongside tools/harvest-wadsworth.cjs (it picks up new lines as they arrive) and stops after
15 minutes with nothing new. Pictures already in the folder are skipped."""
import json, os, re, sys, time, io, urllib.request
from PIL import Image
SRC = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15 (personal museum guide)'
def safe(acc): return re.sub(r'[^A-Za-z0-9._-]+', '_', acc)
seen = set()
idle = 0
while idle < 900:
    rows = [json.loads(l) for l in open(SRC)] if os.path.exists(SRC) else []
    todo = [r for r in rows if r.get('_img') and r.get('Object ID') and r['Object ID'] not in seen]
    if not todo:
        idle += 30; time.sleep(30); continue
    idle = 0
    for r in todo:
        acc = r['Object ID']; seen.add(acc)
        path = f"{OUT}/{safe(acc)}.jpg"
        if os.path.exists(path): continue
        url = 'https://5058.sydneyplus.com' + r['_img'].replace('&amp;', '&')
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60).read()
            im = Image.open(io.BytesIO(data)).convert('RGB')
            im.thumbnail((420, 420))
            im.save(path, 'JPEG', quality=72, optimize=True, progressive=True)
        except Exception as e:
            print('fail', acc, e, flush=True)
        time.sleep(2)
print('done', len(seen), flush=True)
