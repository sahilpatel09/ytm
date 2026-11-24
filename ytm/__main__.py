from __future__ import annotations

import os
import sys
from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual_image.widget import TGPImage


def native_cover_widget() -> type[TGPImage] | None:
    # A Kitty graphics reply alone does not guarantee support for image placeholders.
    if os.environ.get("TERM") not in {"xterm-ghostty", "xterm-kitty"}:
        return None
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None

    # Import before Textual takes over terminal input so the probe can read its reply.
    try:
        from textual_image import renderable
    except (OSError, ZeroDivisionError):
        # Some pseudo-terminals report a zero-sized window until first resize.
        return None

    if renderable.Image is not renderable.TGPImage:
        return None

    from textual_image.widget import TGPImage

    return TGPImage


def main() -> None:
    if sys.argv[1:] == ["--version"]:
        print(f"ytm {metadata.version('ytm')}")
        return

    from ytm.app import YtmApp

    app = YtmApp(native_cover=native_cover_widget())
    try:
        app.run()
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
