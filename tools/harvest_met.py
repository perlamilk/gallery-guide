#!/usr/bin/env python3
"""Harvest every on-view object at The Met Fifth Avenue from the Met's Open Access API.

Saves .cache/met/ids.json and one JSON per object in .cache/met/obj/. Polite: 4 workers,
about 12 requests a second (the API asks for at most 80). Re-running skips what's cached.
"""
import json, os, sys, time, urllib.request, concurrent.futures as cf

B = "https://collectionapi.metmuseum.org/public/collection"
C = os.path.join(os.path.dirname(__file__), "..", ".cache", "met")
UA = {"User-Agent": "gallery-guide/1.0 (museum visitor guide; open access data)"}


def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** i * 2)
        except Exception:
            time.sleep(2 ** i * 2)
    return None


def page_all(q):
    out, off = [], 0
    while True:
        d = get(f"{B}/v1.1/search?isOnView=true&q=*{q}&limit=500&offset={off}") or {}
        got = d.get("objectIDs") or []
        out += got
        if len(got) < 500 or off + 500 >= 10000:
            return out, d.get("total") or 0
        off += 500
        time.sleep(0.4)


def ids():
    """The search pages stop at 10,000 results, so ask department by department, and split
    big departments (Egyptian Art) by date."""
    p = os.path.join(C, "ids.json")
    if os.path.exists(p):
        return json.load(open(p))
    deps = [d["departmentId"] for d in get(f"{B}/v1/departments")["departments"]]
    out = set()
    for dep in deps:
        got, total = page_all(f"&departmentId={dep}")
        if total > 10000:
            # dateBegin/dateEnd keep only objects wholly inside the window, so the windows overlap
            # (to catch objects dated across a boundary), and each is split by hasImages to stay
            # under 10,000 results
            got = []
            wins = [(-500000, -1900), (-2100, -1500), (-1600, -1000), (-1100, -400), (-700, 3000),
                    (-3500, -1000), (-1600, 0), (-500000, 3000)]
            for a, b in wins:
                for im in ("true", "false"):
                    g, t = page_all(f"&departmentId={dep}&dateBegin={a}&dateEnd={b}&hasImages={im}")
                    print("  ", dep, a, b, im, t, len(g), flush=True)
                    got += g
            got = list(set(got))
        out |= set(got)
        print("dept", dep, total, len(got), "all", len(out), flush=True)
    out = sorted(out)
    json.dump(out, open(p, "w"))
    return out


def one(i):
    p = os.path.join(C, "obj", f"{i}.json")
    if os.path.exists(p):
        return
    d = get(f"{B}/v1/objects/{i}")
    json.dump(d, open(p, "w"))
    time.sleep(0.3)


if __name__ == "__main__":
    os.makedirs(os.path.join(C, "obj"), exist_ok=True)
    L = ids()
    with cf.ThreadPoolExecutor(8) as ex:
        for n, _ in enumerate(ex.map(one, L)):
            if n % 1000 == 0:
                print("obj", n, "/", len(L), flush=True)
    print("done")
