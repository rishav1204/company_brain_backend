from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


class UnsafeUrlError(ValueError):
    pass


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Unable to resolve host: {hostname}") from exc
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ip_str = info[4][0]
        try:
            addrs.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    if not addrs:
        raise UnsafeUrlError(f"No resolvable addresses for host: {hostname}")
    return addrs


def validate_outbound_url(url: str) -> str:
    """Validate webhook/outbound URL to mitigate SSRF."""
    raw = (url or "").strip()
    if not raw:
        raise UnsafeUrlError("URL is required")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("URL scheme must be http or https")
    if settings.app_env.lower() == "prod" and parsed.scheme != "https":
        raise UnsafeUrlError("HTTPS is required for outbound URLs in production")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise UnsafeUrlError("URL host is required")
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith(".local"):
        raise UnsafeUrlError("Local or metadata hosts are not allowed")

    try:
        literal = ipaddress.ip_address(hostname)
        if _is_blocked_ip(literal):
            raise UnsafeUrlError("Private or link-local IP addresses are not allowed")
    except ValueError:
        for addr in _resolve_host_ips(hostname):
            if _is_blocked_ip(addr):
                raise UnsafeUrlError("Resolved host points to a private or link-local address")

    if parsed.username or parsed.password:
        raise UnsafeUrlError("Embedded credentials in URL are not allowed")

    return raw
