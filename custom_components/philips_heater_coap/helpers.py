"""Shared network helpers for Philips Heater integration."""
from __future__ import annotations

import asyncio
import logging

from aioairctrl import CoAPClient

_BACKLIGHT_FIELD = "D03105"  # display backlight (0=off, 1=on)

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


async def get_status_via_tickle(client: CoAPClient, timeout: float = 5.0) -> dict | None:
    """Force a CoAP status push by toggling the display backlight.

    Some models won't push on observe registration alone. Tries backlight=0
    first (most common resting state is 1), then backlight=1 if no response.
    Restores the original value after a successful push.
    """
    _LOGGER = logging.getLogger(__name__)
    for write_value in (0, 1):
        # Fresh generator each attempt — a cancelled __anext__() leaves the
        # generator in a broken state and subsequent calls raise StopAsyncIteration.
        observe_gen = client.observe_status()
        try:
            anext_task = asyncio.create_task(observe_gen.__anext__())
            await asyncio.sleep(0.3)  # let the observe GET be dispatched first
            try:
                await client.set_control_value(_BACKLIGHT_FIELD, write_value)
            except Exception:
                pass
            try:
                status = await asyncio.wait_for(anext_task, timeout=timeout)
            except (asyncio.TimeoutError, StopAsyncIteration):
                anext_task.cancel()
                await asyncio.gather(anext_task, return_exceptions=True)
                continue
            try:
                await client.set_control_value(_BACKLIGHT_FIELD, 1 - write_value)
            except Exception:
                pass
            return status
        finally:
            await observe_gen.aclose()
    _LOGGER.warning("Tickle: no status received from device after two attempts")
    return None
