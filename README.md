# Shortest Path Shopping

Pick a saved Google Maps list of shops and get the shortest **walking** route through all of them,
drawn on a map, with turn-by-turn hand-off to Google Maps.

Built for planning a shopping trip in Florence, but it works with any shared Google Maps list.

**Live site:** https://dvh-h.github.io/ShortestPathShopping/

## How it works

```
 Google Maps shared list ──(shop_route.py --add, run by a person)──▶ lists/<name>.json
                                                                            │
 Browser (index.html) ◀── static files on GitHub Pages ◀───────────────────┘
        │
        ├─ OSRM (routing.openstreetmap.de, foot profile) ─▶ walking-time matrix + street geometry
        ├─ solves the shortest path in JavaScript (exact for ≤ 13 stops, heuristic above)
        └─ Leaflet + OpenStreetMap tiles ─▶ numbered pins and route line
```

There is **no backend**. The site is static files; everything dynamic happens in the visitor's browser.

### Why lists are saved in the repo instead of fetched live
Google's shared-list page loads its data via an undocumented JSON endpoint
(`maps/preview/entitylist/getlist`) with no CORS headers, so a browser cannot call it from another site.
A server-side proxy (tried with a Cloudflare Worker) is answered with **HTTP 429 "unusual traffic"** because Google
rejects requests from datacenter IP ranges. The same call works from a normal home connection, so
lists are fetched by a person running `shop_route.py` (or optionally a GitHub Action, see below) and committed as JSON.

### Route calculation
- **Distance metric:** walking duration from OSRM's `/table` endpoint (`https://routing.openstreetmap.de/routed-foot`).
  The public `router.project-osrm.org` demo only has a car profile, so it is not used.
- **Solver:** open path (no return) or round trip. ≤ 13 stops: exact Held–Karp DP. More: nearest-neighbour followed by 2-opt.
  If no start is chosen, every stop is tried as the start and the cheapest result wins.
- **Fallback:** if OSRM is unreachable the page falls back to straight-line distance at 5 km/h and says so.
- **Google Maps hand-off:** routes are split into links of 10 stops (consecutive links share one stop), because
  Google Maps directions URLs only accept a limited number of waypoints.

## Repository layout

| Path | Purpose |
|---|---|
| `index.html` | The whole front end (HTML, CSS, JS in one file; Leaflet from cdnjs). |
| `lists/index.json` | Registry that fills the dropdown: `[{ "name": "...", "file": "x.json", "profiles": ["k","d"] }]`. |
| `lists/*.json` | One file per saved list (format below). |
| `shop_route.py` | Python 3 CLI, standard library only: fetches lists, saves them, and can compute a route in the terminal. |
| `.github/workflows/add-list.yml` | Optional "paste a link" GitHub Action (see below). |

### List file format
```json
{
  "title": "Firenze vintage",
  "places": [
    { "name": "Leonardo Shoes", "address": "Via dei Cerchi, 5R, 50122 Firenze FI", "lat": 43.7705, "lon": 11.2560 }
  ]
}
```
Hand-written lists work too; only `name`, `lat` and `lon` are required (`address` may be empty).

## Profiles
The page has a "Who are you?" selector (currently `k` and `d`, defined in `PROFILES` in `index.html`) so each person only sees their own lists.
The choice is remembered in the browser's `localStorage`.

- A list is shown to a profile when its `profiles` array in `lists/index.json` contains it.
- A list with **no** `profiles` key is shown to **everyone**.
- This is a convenience filter, **not security**: the list files are public in the repo and anyone can switch profile.
- To add a profile, add it to `PROFILES` in `index.html` and to the lists it should see.

## Adding a list

### From your own machine (reliable)
Requires Python 3.8+. No dependencies.
```bash
python shop_route.py "https://maps.app.goo.gl/XXXXXXXX" --add "Name shown in dropdown" --profiles k,d
git add lists && git commit -m "Add list" && git push
```
`--add` resolves the link, downloads the list, writes `lists/<slug>.json` and updates `lists/index.json`.
`--profiles` says who sees it (omit it for everyone; re-adding an existing list without `--profiles` keeps its current visibility).
Google sometimes answers with an empty result for valid lists, so the script retries up to 6 times.
Places without coordinates are geocoded with Nominatim (rate limited to 1 request/second, per their usage policy).
Pages redeploys within a minute or two.

### From GitHub (best effort)
Actions → **Add shopping list** → *Run workflow* → paste link, name and profiles (default `k,d`). It runs the same command on a GitHub runner and
commits the result. **This may fail with a 429 from Google**, because runners are datacenter IPs like any other.
If it does, use the command above.

## Other CLI usage
```bash
python shop_route.py "<link>"                            # print the route (straight-line distances)
python shop_route.py "<link>" --start "Leonardo" --round-trip
python shop_route.py "<link>" --export out.json          # dump the raw list without registering it
```
The CLI uses straight-line distance; the website uses real walking times, so the two can order stops differently.

## Run locally
Any static file server works (the page uses `fetch`, so opening the file directly will not):
```bash
python -m http.server 8765
# open http://localhost:8765
```

## Deploy
GitHub repo → Settings → Pages → *Deploy from a branch* → `main` / `/ (root)`.
Pages serves files with a 10-minute browser cache; the page fetches `lists/` with `cache: "no-cache"` so new lists appear
immediately, but `index.html` itself can lag behind by up to 10 minutes after a deploy.

## Limitations
- The Google list endpoint is **unofficial** and could change or disappear without notice. If `--add` starts failing,
  the parsing in `fetch_list()` (`shop_route.py`) is the place to look.
- Lists are capped at 500 places by the request (`!4i500`); OSRM's public server limits table size, so very large lists may fail.
- OSRM and tile servers are free public services intended for light use. Do not use this for heavy traffic.
- No license has been chosen yet; add one if you want others to reuse the code.

## Credits
Routing by [OSRM](https://project-osrm.org/) on the OpenStreetMap Germany server, map data © [OpenStreetMap](https://www.openstreetmap.org/copyright)
contributors, maps rendered with [Leaflet](https://leafletjs.com/), geocoding by [Nominatim](https://nominatim.org/).
