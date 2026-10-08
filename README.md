# Shortest Path Shopping

Takes a shared Google Maps list and finds the shortest walking route through all places.
Static site, no backend: host it on GitHub Pages.

- `index.html` – the website (OSRM walking distances + Leaflet map).
- `shop_route.py` – optional command-line version; `--export file.json` dumps a list to JSON.

## Publish
Push to GitHub, then Settings → Pages → Deploy from branch → `main` / root.

## Adding a shopping list
Google blocks cloud servers from reading lists, so lists are saved as files in `lists/` and the site shows a dropdown.

**On your PC (always works):**
```
python shop_route.py "https://maps.app.goo.gl/XXXX" --add "Firenze vintage"
git add lists && git commit -m "Add list" && git push
```

**From GitHub (may be blocked by Google):** Actions tab → *Add shopping list* → Run workflow → paste the link and a name.
If it fails with a 429 error, Google blocked GitHub's servers; use the PC command instead.

The Google list endpoint is unofficial and may change.
