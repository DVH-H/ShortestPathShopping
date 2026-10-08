"""Fetch a shared Google Maps list and compute the shortest walking-ish route through it.

Usage:
    python shop_route.py <google-maps-list-url> [--start "Place name"] [--round-trip]

Steps:
 1. Resolve the short link and extract the list id.
 2. Fetch the list from Google's (unofficial) entitylist endpoint -> names, addresses, lat/lon.
 3. Any place without coordinates is geocoded with Nominatim (max 1 request/second).
 4. Solve the shortest path (exact Held-Karp up to 13 stops, else nearest-neighbour + 2-opt).
"""
import argparse
import itertools
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "shortestpathshopping/0.1 (personal project)"


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")


def extract_list_id(url):
    final_url, _ = http_get(url) if "goo.gl" in url else (url, "")
    # Final URL looks like .../data=!3m1!4b1!4m3!11m2!2s<LISTID>!3e3
    m = re.search(r"!2s([A-Za-z0-9_-]{16,})", urllib.parse.unquote(final_url))
    if not m:
        m = re.search(r"placelists/list/([A-Za-z0-9_-]+)", final_url)
    if not m:
        sys.exit(f"Could not find list id in {final_url}")
    return m.group(1)


def fetch_list(list_id):
    pb = f"!1m1!1s{list_id}!2e2!3e2!4i500!16b1"
    url = f"https://www.google.com/maps/preview/entitylist/getlist?authuser=0&hl=en&gl=dk&pb={pb}"
    # Google intermittently answers with an empty result ([null,null,[3,id]]) even for valid lists, so retry.
    for attempt in range(1, 7):
        try:
            _, body = http_get(url)
            data = json.loads(body.split("\n", 1)[1])[0]  # strip )]}' prefix, unwrap
        except (IndexError, ValueError, OSError) as e:
            body, data = str(e), None
        if data and len(data) >= 9:
            break
        print(f"  attempt {attempt}: no list data, retrying...", file=sys.stderr)
        time.sleep(2 * attempt)
    else:
        sys.exit("Google did not return the list (blocked, private or deleted?). Last reply started with:\n" + body[:300])
    title = data[4]
    places = []
    for item in data[8] or []:
        loc = item[1]
        coords = loc[5] if len(loc) > 5 and loc[5] else None
        places.append({
            "name": item[2],
            "address": loc[4] or loc[2],
            "lat": coords[2] if coords else None,
            "lon": coords[3] if coords else None,
        })
    return title, places


def nominatim(query):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1})
    _, body = http_get(url)
    res = json.loads(body)
    time.sleep(1.1)  # usage policy: max 1 req/s
    return (float(res[0]["lat"]), float(res[0]["lon"])) if res else None


def haversine(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def held_karp(d, start, round_trip):
    n = len(d)
    others = [i for i in range(n) if i != start]
    # cost[(mask, j)] = best cost starting at `start`, visiting mask, ending at j
    cost, parent = {}, {}
    for j in others:
        cost[(1 << j, j)] = d[start][j]
    for size in range(2, len(others) + 1):
        for subset in itertools.combinations(others, size):
            mask = sum(1 << j for j in subset)
            for j in subset:
                prev = mask ^ (1 << j)
                best = min((cost[(prev, k)] + d[k][j], k) for k in subset if k != j)
                cost[(mask, j)], parent[(mask, j)] = best
    full = sum(1 << j for j in others)
    end = min(others, key=lambda j: cost[(full, j)] + (d[j][start] if round_trip else 0))
    path, mask, j = [], full, end
    while j is not None:
        path.append(j)
        k = parent.get((mask, j))
        mask ^= 1 << j
        j = k
    return [start] + path[::-1]


def length(path, d, round_trip):
    total = sum(d[a][b] for a, b in zip(path, path[1:]))
    return total + (d[path[-1]][path[0]] if round_trip else 0)


def heuristic(d, start, round_trip):
    n = len(d)
    path, left = [start], set(range(n)) - {start}
    while left:
        nxt = min(left, key=lambda j: d[path[-1]][j])
        path.append(nxt)
        left.remove(nxt)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = path[:i] + path[i:k + 1][::-1] + path[k + 1:]
                if length(cand, d, round_trip) < length(path, d, round_trip) - 1e-9:
                    path, improved = cand, True
    return path


def solve(d, start, round_trip):
    return held_karp(d, start, round_trip) if len(d) <= 13 else heuristic(d, start, round_trip)


def save_list(name, title, places):
    """Store a list in lists/ and register it in lists/index.json (what the website's dropdown reads)."""
    import os
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lists")
    os.makedirs(folder, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "list"
    with open(os.path.join(folder, slug + ".json"), "w", encoding="utf-8") as f:
        json.dump({"title": name, "places": places}, f, ensure_ascii=False, indent=1)
    index_path = os.path.join(folder, "index.json")
    index = json.load(open(index_path, encoding="utf-8")) if os.path.exists(index_path) else []
    index = [e for e in index if e["file"] != slug + ".json"] + [{"name": name, "file": slug + ".json"}]
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(sorted(index, key=lambda e: e["name"].lower()), f, ensure_ascii=False, indent=1)
    print(f"Saved {len(places)} places to lists/{slug}.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--start", help="Name (substring) of the place to start at; default = best start")
    ap.add_argument("--export", help="Write the places to this JSON file and exit")
    ap.add_argument("--add", metavar="NAME", help="Save the list as lists/<name>.json and register it for the website, then exit")
    ap.add_argument("--round-trip", action="store_true", help="Return to the starting place")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    title, places = fetch_list(extract_list_id(args.url))
    print(f"List: {title} ({len(places)} places)")

    for p in places:
        if p["lat"] is None:
            print(f"  geocoding {p['name']} via Nominatim...")
            hit = nominatim(f"{p['name']}, {p['address']}") or nominatim(p["address"])
            if hit:
                p["lat"], p["lon"] = hit
    places = [p for p in places if p["lat"] is not None]
    if args.add:
        save_list(args.add, title, places)
        return
    if args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump({"title": title, "places": places}, f, ensure_ascii=False, indent=1)
        print(f"Wrote {len(places)} places to {args.export}")
        return

    pts = [(p["lat"], p["lon"]) for p in places]
    d = [[haversine(a, b) for b in pts] for a in pts]

    if args.start:
        starts = [i for i, p in enumerate(places) if args.start.lower() in p["name"].lower()]
        if not starts:
            sys.exit(f"No place matching {args.start!r}")
    else:
        starts = range(len(places))
    best = min((solve(d, s, args.round_trip) for s in starts),
               key=lambda pth: length(pth, d, args.round_trip))

    print(f"\nRoute ({length(best, d, args.round_trip):.2f} km straight-line):")
    for n, i in enumerate(best, 1):
        leg = f"  (+{d[best[n - 2]][i] * 1000:.0f} m)" if n > 1 else ""
        print(f"{n:2}. {places[i]['name']} - {places[i]['address']}{leg}")

    stops = "/".join(f"{places[i]['lat']},{places[i]['lon']}" for i in best)
    print(f"\nGoogle Maps (walking): https://www.google.com/maps/dir/{stops}/data=!4m2!4m1!3e2")


if __name__ == "__main__":
    main()
