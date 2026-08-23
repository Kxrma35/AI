import socket
from concurrent.futures import ThreadPoolExecutor

import dns.resolver
import whois as whois_lib

MAX_PORTS_PER_SCAN = 1024
DNS_RECORD_TYPES = ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]


def port_scan(host: str, ports: str = "1-1024", timeout: float = 0.5) -> dict:
    try:
        if "-" in ports:
            start_s, end_s = ports.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(ports)
    except ValueError:
        return {"error": f"Invalid port range: {ports!r}. Use a single port or 'start-end'."}

    if end < start:
        return {"error": "End port must be >= start port"}
    if (end - start + 1) > MAX_PORTS_PER_SCAN:
        return {"error": f"Port range too large — max {MAX_PORTS_PER_SCAN} ports per scan"}

    def check_port(port):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return port
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(check_port, range(start, end + 1)))

    open_ports = sorted(p for p in results if p is not None)
    return {"host": host, "ports_scanned": f"{start}-{end}", "open_ports": open_ports}


MAX_RECORDS_PER_TYPE = 8
MAX_RECORD_LENGTH = 150


def dns_lookup(domain: str) -> dict:
    records = {}
    for record_type in DNS_RECORD_TYPES:
        try:
            answers = dns.resolver.resolve(domain, record_type)
            values = [str(r)[:MAX_RECORD_LENGTH] for r in answers][:MAX_RECORDS_PER_TYPE]
            records[record_type] = values
        except Exception:
            records[record_type] = []
    return {"domain": domain, "records": records}


def whois_lookup(domain: str) -> dict:
    try:
        w = whois_lib.whois(domain)
        return {
            "domain": domain,
            "registrar": w.get("registrar"),
            "creation_date": str(w.get("creation_date")),
            "expiration_date": str(w.get("expiration_date")),
            "name_servers": w.get("name_servers"),
            "status": w.get("status"),
        }
    except Exception as e:
        return {"error": str(e)}
