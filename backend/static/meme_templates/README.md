# Meme template manifest

`templates.json` is an allowlist of manually reviewed, text-free source images.
The renderer reads the checked-in assets from `open/`, crops transparent padding,
and places them on a compact 480 × 480 caption canvas. The caption height controls
the available illustration area so the subject stays visually connected to the
text. `backend/scripts/import_open_meme_templates.py` documents the upstream
download URL for every imported binary asset.

Every entry includes its source page and media license. The current set uses
OpenMoji (CC BY-SA 4.0), selected MemeTastic extras (CC0 1.0), and one explicitly
public-domain Wikimedia Commons drawing. ChineseBQB and Memegen raster templates
are not bundled because an open-source code license does not automatically license
third-party meme images.

The four `original_*.png` reaction characters were generated specifically for
this project with OpenAI image generation and then manually selected. They do not
copy an existing meme character, contain no baked-in text, and are marked
`Project Original` in the manifest. Their intended product role is social chat
replies; the OpenMoji set remains available as a secondary basic-emotion group.

Attribution for OpenMoji: “All emojis designed by OpenMoji – the open-source emoji
and icon project. License: CC BY-SA 4.0.” Generated adaptations containing an
OpenMoji graphic must remain available under CC BY-SA 4.0.
