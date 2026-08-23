import json
import os
import socket
import ssl
import subprocess
import sys
from datetime import datetime, timezone

import httpx

SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]


def check_ssl_cert(domain: str, port: int = 443) -> dict:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        not_after = cert.get("notAfter")
        days_left = None
        if not_after:
            expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days_left = (expires - datetime.now(timezone.utc)).days

        return {
            "domain": domain,
            "issuer": dict(x[0] for x in cert.get("issuer", [])),
            "subject": dict(x[0] for x in cert.get("subject", [])),
            "expires": not_after,
            "days_until_expiry": days_left,
        }
    except Exception as e:
        return {"error": str(e)}


def check_security_headers(url: str) -> dict:
    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=True)
        present = {h: r.headers.get(h) for h in SECURITY_HEADERS if h in r.headers}
        missing = [h for h in SECURITY_HEADERS if h not in r.headers]
        return {"url": url, "status_code": r.status_code, "present": present, "missing": missing}
    except Exception as e:
        return {"error": str(e)}


def check_python_dependencies(path: str = ".") -> dict:
    req_file = os.path.join(path, "requirements.txt")
    if not os.path.exists(req_file):
        return {"error": f"No requirements.txt found at {req_file}"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-r", req_file, "--format", "json"],
            capture_output=True, text=True, timeout=60,
        )
        try:
            data = json.loads(result.stdout)
            vulnerable = [d for d in data.get("dependencies", []) if d.get("vulns")]
            return {"requirements_file": req_file, "vulnerable_packages": vulnerable, "total_checked": len(data.get("dependencies", []))}
        except json.JSONDecodeError:
            return {"requirements_file": req_file, "raw_output": (result.stdout or result.stderr)[:3000]}
    except Exception as e:
        return {"error": str(e)}
