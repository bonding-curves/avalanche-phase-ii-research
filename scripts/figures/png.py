"""Render a saved HoloViews or Bokeh HTML chart to PNG with a headless Chromium.

The browser is the one named by ``CHROME_HEADLESS``, else the newest Playwright headless shell under
``~/.cache/ms-playwright``, else ``chromium`` or ``google-chrome`` on the path. The page loads BokehJS from its CDN, so
rendering needs network access.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def browser() -> str:
    named = os.environ.get("CHROME_HEADLESS")
    if named:
        return named
    shells = sorted(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
    if shells:
        return str(shells[-1])
    for name in ("chromium", "google-chrome", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("no headless Chromium found: set CHROME_HEADLESS to a Chromium or chrome-headless-shell binary")


def save_png(html: Path, png: Path, width: int, height: int) -> Path:
    """Screenshot ``html`` at ``width`` by ``height`` pixels into ``png`` and return it."""
    png.unlink(missing_ok=True)
    subprocess.run([browser(), "--headless", "--hide-scrollbars", "--force-device-scale-factor=2", f"--window-size={width},{height}",
                    "--virtual-time-budget=15000", f"--screenshot={png.resolve()}", html.resolve().as_uri()],
                   check=True, capture_output=True, timeout=120)
    if not png.is_file() or png.stat().st_size < 10_000:
        raise RuntimeError(f"the screenshot of {html} is missing or blank")
    return png
