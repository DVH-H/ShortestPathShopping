# Shortest Path Shopping

Takes a shared Google Maps list and finds the shortest walking route through all places.
Static site, no backend: host it on GitHub Pages.

- `index.html` – the website (OSRM walking distances + Leaflet map).
- `shop_route.py` – optional command-line version; `--export file.json` dumps a list to JSON.

## Publish
Push to GitHub, then Settings → Pages → Deploy from branch → `main` / root.

## Using it
Google blocks cloud servers from reading lists, so the list is read in *your own* browser:
1. One-time: add the **Load list** bookmark from the site (drag it to the bookmarks bar, or use *Copy bookmark code* and paste it as the address of a new bookmark).
2. Open the shared Google Maps list link in the browser.
3. Tap the **Load list** bookmark – you are sent back to the site with the list loaded.

The list data travels in the URL fragment (`#d=…`), which is never sent to any server.
The Google list endpoint is unofficial and may change.
