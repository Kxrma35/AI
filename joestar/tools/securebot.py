import os
import time
import httpx

_token_cache = {"token": None, "expires_at": 0}


def _base_url() -> str | None:
    url = os.getenv("SECUREBOT_URL", "").rstrip("/")
    return url or None


def _login(base_url: str) -> str | None:
    username = os.getenv("SECUREBOT_USERNAME", "")
    password = os.getenv("SECUREBOT_PASSWORD", "")
    r = httpx.post(f"{base_url}/api/login", json={"username": username, "password": password}, timeout=10)
    if r.status_code != 200:
        return None
    token = r.json().get("token")
    if token:
        _token_cache["token"] = token
        _token_cache["expires_at"] = time.time() + 3300  # renew a bit before the server's 1hr TTL
    return token


def _get_token(base_url: str, force: bool = False) -> str | None:
    if not force and _token_cache["token"] and _token_cache["expires_at"] > time.time():
        return _token_cache["token"]
    return _login(base_url)


def get_securebot_status() -> dict:
    """Fetch current telemetry and recent tamper alerts from the SecureBot IoT security pipeline."""
    base_url = _base_url()
    if not base_url:
        return {"reachable": False, "error": "SecureBot is not configured (set SECUREBOT_URL in .env)."}

    try:
        token = _get_token(base_url)
        if not token:
            return {"reachable": False, "error": "Could not authenticate with SecureBot — check SECUREBOT_USERNAME/SECUREBOT_PASSWORD."}

        headers = {"Authorization": f"Bearer {token}"}
        telemetry_resp = httpx.get(f"{base_url}/api/telemetry", headers=headers, timeout=10)
        if telemetry_resp.status_code == 401:
            token = _get_token(base_url, force=True)
            if not token:
                return {"reachable": False, "error": "SecureBot rejected authentication."}
            headers = {"Authorization": f"Bearer {token}"}
            telemetry_resp = httpx.get(f"{base_url}/api/telemetry", headers=headers, timeout=10)

        alerts_resp = httpx.get(f"{base_url}/api/alerts", headers=headers, timeout=10)
        telemetry = telemetry_resp.json() if telemetry_resp.status_code == 200 else {}
        alerts = alerts_resp.json() if alerts_resp.status_code == 200 else []

        return {
            "reachable": True,
            "latest_telemetry": telemetry,
            "recent_alerts": alerts[:5],
            "alert_count": len(alerts),
        }
    except httpx.RequestError as e:
        return {"reachable": False, "error": f"SecureBot unreachable: {e}"}
    except Exception as e:
        return {"reachable": False, "error": f"Unexpected error contacting SecureBot: {e}"}
