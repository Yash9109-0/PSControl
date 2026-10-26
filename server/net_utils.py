"""Network utilities for WebSocket handling and connection management."""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional


def get_lan_ip() -> str:
    """Return the PC's LAN IP address.

    Prefers a private RFC 1918 address (192.168.x.x, 10.x.x.x, or 172.16-31.x.x)
    so the QR code and join URL point at an address other phones on the same Wi-Fi
    can actually reach. Falls back to any non-loopback address, then 127.0.0.1.
    """
    candidates: list[str] = []

    try:
        hostname = socket.gethostname()
        candidates.extend(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass

    # Fallback: open a throwaway UDP connection to discover the local
    # interface that would reach a public address.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        candidates.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass

    # First pass: check RFC 1918 private IPv4 addresses
    for raw_ip in candidates:
        try:
            ip_obj = ipaddress.ip_address(raw_ip)
            if ip_obj.version == 4 and ip_obj.is_private and not ip_obj.is_loopback:
                return raw_ip
        except ValueError:
            pass

    # Second pass: any non-loopback
    for raw_ip in candidates:
        try:
            ip_obj = ipaddress.ip_address(raw_ip)
            if not ip_obj.is_loopback:
                return raw_ip
        except ValueError:
            pass

    return "127.0.0.1"


def is_localhost(host: Optional[str]) -> bool:
    """True if ``host`` is a loopback/localhost address."""
    if not host:
        return False
    if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "testclient"):
        return True
    if host.startswith("::1") or host.startswith("::ffff:127."):
        return True
    return False
