"""License API client — gọi Google Apps Script API để validate key."""

import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timedelta

from licensing.fingerprint import get_hardware_id
from licensing import storage

API_URL = "https://script.google.com/macros/s/AKfycbwHjQYei5vgWLft5jfiZAJ1trDCBSIyqbFv5SqwRWzOLZ-Rr3pQgf3MqA8fdSv2hxfC8g/exec"

OFFLINE_GRACE_DAYS = 7


def set_api_url(url: str):
    global API_URL
    API_URL = url


def _api_call(payload: dict) -> dict:
    """Gọi Google Apps Script API. Xử lý redirect tự động."""
    data = json.dumps(payload).encode("utf-8")

    # Google Apps Script redirect POST → GET, cần follow redirect manually
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPRedirectHandler(),
    )

    req = urllib.request.Request(
        API_URL, data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AutoCapCut",
        },
    )

    try:
        with opener.open(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # Google Apps Script returns 302 redirect for POST
        if e.code in (302, 301, 307):
            redirect_url = e.headers.get("Location", "")
            if redirect_url:
                req2 = urllib.request.Request(
                    redirect_url, data=data,
                    headers={"Content-Type": "application/json"},
                )
                with opener.open(req2, timeout=15) as resp:
                    return json.loads(resp.read().decode())
        raise


def activate(key: str) -> tuple[bool, str]:
    """Activate key. Returns (success, message)."""
    if not API_URL:
        return False, "API URL not configured"

    hw_id = get_hardware_id()

    try:
        result = _api_call({
            "action": "activate",
            "key": key,
            "hardware_id": hw_id,
        })
    except Exception as e:
        return False, f"Connection error: {e}"

    if result.get("success"):
        storage.save_license({
            "key": key,
            "hardware_id": hw_id,
            "activated_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
            "expires_at": result.get("expires_at", ""),
        })
        return True, result.get("message", "Activated!")
    else:
        return False, result.get("message", "Activation failed")


def is_licensed() -> bool:
    """Check if current machine has valid license."""
    data = storage.load_license()
    if not data:
        return False

    # Check offline grace period
    last_validated = data.get("last_validated", "")
    if last_validated:
        try:
            last_dt = datetime.fromisoformat(last_validated)
            if datetime.now() - last_dt < timedelta(days=OFFLINE_GRACE_DAYS):
                return True
        except Exception:
            pass

    # Try online validation
    if not API_URL:
        return bool(data.get("key"))

    try:
        ok, _ = validate_online(data)
        return ok
    except Exception:
        return bool(data.get("key"))


def validate_online(data: dict) -> tuple[bool, str]:
    """Validate license online."""
    result = _api_call({
        "action": "validate",
        "key": data.get("key", ""),
        "hardware_id": get_hardware_id(),
    })

    if result.get("success"):
        data["last_validated"] = datetime.now().isoformat()
        data["expires_at"] = result.get("expires_at", data.get("expires_at", ""))
        storage.save_license(data)
        return True, "Valid"
    else:
        return False, result.get("message", "Invalid license")
