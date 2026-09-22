"""Download the small, explicitly licensed template set used by the app.

This is a maintainer tool, not a runtime dependency. It deliberately avoids
popular movie/celebrity meme images whose source repository has no media
license. Run from ``backend/`` after installing Pillow and CairoSVG.
"""

import io
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image


TARGET = Path(__file__).resolve().parent.parent / "static" / "meme_templates" / "open"
OPENMOJI_COMMIT = "aeb8bb3a59e2de39c754ac79180c8131c906acea"
MEMETASTIC_COMMIT = "0c12a2754d50c5ab208af1abed3f82b28ff1fd33"
OPENMOJI_BASE = f"https://raw.githubusercontent.com/hfg-gmuend/openmoji/{OPENMOJI_COMMIT}/color/618x618"
OPENMOJI = {
    "openmoji_joy.png": "1F602",
    "openmoji_thinking.png": "1F914",
    "openmoji_crying.png": "1F62D",
    "openmoji_suspicious.png": "1F928",
    "openmoji_mind_blown.png": "1F92F",
    "openmoji_rolling_eyes.png": "1F644",
    "openmoji_clown.png": "1F921",
    "openmoji_smirk.png": "1F60F",
}


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "meme-template-import/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def save_png(name: str, content: bytes, max_size: tuple[int, int] = (900, 900)) -> None:
    image = Image.open(io.BytesIO(content)).convert("RGBA")
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    image.save(TARGET / name, "PNG", optimize=True)


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, code in OPENMOJI.items():
        save_png(name, download(f"{OPENMOJI_BASE}/{code}.png"))

    save_png(
        "duff_reaction.png",
        download(
            "https://upload.wikimedia.org/wikipedia/commons/a/a0/Duff_reaction.png"
        ),
    )

    pokerface_svg = download(
        f"https://raw.githubusercontent.com/gsantner/memetastic/{MEMETASTIC_COMMIT}/"
        "extras/meme__pokerface.svg"
    )
    pokerface_png = cairosvg.svg2png(
        bytestring=pokerface_svg, output_width=700, output_height=700
    )
    save_png("memetastic_pokerface.png", pokerface_png)


if __name__ == "__main__":
    main()
