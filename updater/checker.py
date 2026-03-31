"""Update checker — check GitHub Releases for new version."""

import json
import urllib.request
from version import __version__

# TODO: đổi thành repo thật
GITHUB_REPO = "docs8nguyenphuoc-svg/Auto-Capcut"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_for_update() -> dict | None:
    """Returns {'version': '1.1.0', 'download_url': '...'} hoặc None."""
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "AutoCapCut"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        tag = data.get("tag_name", "").lstrip("v")
        if not tag or not _is_newer(tag, __version__):
            return None

        for asset in data.get("assets", []):
            if asset["name"].endswith(".exe"):
                return {
                    "version": tag,
                    "download_url": asset["browser_download_url"],
                    "notes": data.get("body", ""),
                }
    except Exception:
        pass
    return None


def _is_newer(remote: str, local: str) -> bool:
    """Compare version strings: '1.1.0' > '1.0.0'."""
    try:
        r = tuple(int(x) for x in remote.split("."))
        l = tuple(int(x) for x in local.split("."))
        return r > l
    except Exception:
        return False
