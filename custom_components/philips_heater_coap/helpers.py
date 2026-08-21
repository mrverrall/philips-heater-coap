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
    """Request a status push by writing to a functionless control field.

    The observation must be active before the write because the resulting push
    can arrive immediately. Two values are tried per round because some firmware
    only pushes when the written value changes. Multiple rounds tolerate packet
    loss from NON-confirmable CoAP messages.
    """
    for _ in range(rounds):
        for tickle_value in (0, 1):
            # A timed-out __anext__ cannot be reused, so each attempt needs a new
            # observation and its own tasks.
            observe_gen = client.observe_status()
            anext_task = asyncio.create_task(observe_gen.__anext__())
            write_task: asyncio.Task | None = None
            try:
                await asyncio.sleep(0.3)  # Allow the observe GET to reach the device.

                # Do not await the write directly: its response may never arrive
                # offline. The observed status is the success signal and timeout.
                write_task = asyncio.create_task(
                    client.set_control_value(_TICKLE_FIELD, tickle_value)
                )
                try:
                    return await asyncio.wait_for(anext_task, timeout=timeout)
                except (asyncio.TimeoutError, StopAsyncIteration):
                    continue
            finally:
                # Drain cancellation before closing the generator to avoid leaving
                # CoAP request tasks attached to this attempt.
                anext_task.cancel()
                tasks = [anext_task]
                if write_task is not None:
                    write_task.cancel()
                    tasks.append(write_task)
                await asyncio.gather(*tasks, return_exceptions=True)
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
