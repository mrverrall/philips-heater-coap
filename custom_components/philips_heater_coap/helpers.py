"""Shared network helpers for Philips Heater integration."""
from __future__ import annotations

import asyncio
import logging
import socket

from aioairctrl import CoAPClient
from aioairctrl.coap.encryption import DigestMismatchException

# A response was received, but aioairctrl could not decode its encrypted status
# payload. These errors prove the device responded even though its state is unusable.
MALFORMED_STATUS_ERRORS = (DigestMismatchException, KeyError, ValueError)

# Functionless on both device families (see DEVICE_MAPPING.md) but writes reliably
# trigger a control status push, so there's no prior value to save/restore.
_TICKLE_FIELD = "D03182"

_LOGGER = logging.getLogger(__name__)
_COAP_CLIENT_CREATE_LOCK = asyncio.Lock()


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
    # The transport override is process-global, so client creation must not overlap.
    async with _COAP_CLIENT_CREATE_LOCK:
        from aiocoap import defaults as _aiocoap_defaults

        original_transports = _aiocoap_defaults.get_default_clienttransports
        _aiocoap_defaults.get_default_clienttransports = (
            lambda *args, **kwargs: iter(["udp6"])
        )
        try:
            return await CoAPClient.create(host)
        finally:
            _aiocoap_defaults.get_default_clienttransports = original_transports


async def get_status_via_tickle(client: CoAPClient, timeout: float = 5.0, rounds: int = 1) -> dict | None:
    """Force a CoAP status push by writing to a functionless control field.

    Some models won't push on observe registration alone. Tries two different
    values in case the device only pushes on an actual value change, repeated
    for `rounds` passes to ride out isolated packet loss (these are NON-confirmable
    CoAP messages, so a single lost write or reply otherwise looks like silence).
    """
    for _ in range(rounds):
        for tickle_value in (0, 1):
            # Fresh generator each attempt — a cancelled __anext__() leaves the
            # generator in a broken state and subsequent calls raise StopAsyncIteration.
            observe_gen = client.observe_status()
            try:
                anext_task = asyncio.create_task(observe_gen.__anext__())
                await asyncio.sleep(0.3)  # let the observe GET be dispatched first
                try:
                    await client.set_control_value(_TICKLE_FIELD, tickle_value)
                except Exception:
                    pass
                try:
                    return await asyncio.wait_for(anext_task, timeout=timeout)
                except (asyncio.TimeoutError, StopAsyncIteration):
                    anext_task.cancel()
                    await asyncio.gather(anext_task, return_exceptions=True)
                    continue
            finally:
                await observe_gen.aclose()
    _LOGGER.warning("Tickle: no status received from device after %d round(s)", rounds)
    return None


def check_network_reachable(host: str, port: int = 5683) -> bool:
    """Best-effort, non-blocking check for gross network reachability to host.

    UDP has no handshake, so this can't confirm the device itself is alive —
    it only catches failures like routing/ARP errors, for diagnostic logging.
    Run via the executor since name resolution can block.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((host, port))
        return True
    except OSError as err:
        _LOGGER.debug("Network reachability check failed for %s: %s", host, err)
        return False
