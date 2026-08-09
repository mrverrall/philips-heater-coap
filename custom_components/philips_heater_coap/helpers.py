"""Shared network helpers for Philips Heater integration."""
from __future__ import annotations

import logging

from aioairctrl import CoAPClient

_LOGGER = logging.getLogger(__name__)


def arp_lookup_mac(ip: str) -> str | None:
    """Return MAC address for ip from the OS ARP cache, or None."""
    try:
        with open("/proc/net/arp") as f:
            entries = f.read()
        for line in entries.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == ip and parts[3] != "00:00:00:00:00:00":
                return parts[3]
    except OSError as err:
        _LOGGER.debug("ARP cache read failed: %s", err)
    return None


def arp_lookup_ip(mac: str) -> str | None:
    """Return IP address for mac from the OS ARP cache, or None."""
    mac_lower = mac.lower()
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[3].lower() == mac_lower:
                    return parts[0]
    except OSError:
        pass
    return None


async def create_coap_client(host: str) -> CoAPClient:
    """Create a CoAP client restricted to UDP transport.

    Avoids the blocking filesystem scan triggered by aiocoap's TLS transport
    initialisation on Python 3.14+.
    """
    from aiocoap import defaults as _aiocoap_defaults
    _orig = _aiocoap_defaults.get_default_clienttransports
    _aiocoap_defaults.get_default_clienttransports = lambda *a, **kw: iter(["udp6"])
    try:
        return await CoAPClient.create(host)
    finally:
        _aiocoap_defaults.get_default_clienttransports = _orig
