# Meme template manifest

`templates.json` is an allowlist of manually reviewed, text-free source images.
The renderer reads the checked-in assets from `open/` and places them on a new
480 × 480 caption canvas. `backend/scripts/import_open_meme_templates.py`
documents the upstream download URL for every binary asset.

Every entry includes its source page and media license. The current set uses
OpenMoji (CC BY-SA 4.0), selected MemeTastic extras (CC0 1.0), and one explicitly
public-domain Wikimedia Commons drawing. ChineseBQB and Memegen raster templates
are not bundled because an open-source code license does not automatically license
third-party meme images.

Attribution for OpenMoji: “All emojis designed by OpenMoji – the open-source emoji
and icon project. License: CC BY-SA 4.0.” Generated adaptations containing an
OpenMoji graphic must remain available under CC BY-SA 4.0.
