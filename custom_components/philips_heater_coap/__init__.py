"""Philips Heater integration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aioairctrl import CoAPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN, PhilipsApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.NUMBER, Platform.SENSOR]
STORAGE_VERSION = 1
STORAGE_KEY = "philips_heater_coap"
WATCHDOG_TIMEOUT = 86400  # seconds without update before reconnecting
RECONNECT_DELAY_INITIAL = 30  # seconds before first reconnect attempt
RECONNECT_DELAY_MAX = 3600  # max seconds between reconnect attempts (1 hour)


class HeaterObserveCoordinator:
    """Coordinator for Philips Heater using CoAP observe (push updates)."""

    def __init__(self, hass: HomeAssistant, host: str, entry_id: str) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.host = host
        self.status: dict[str, Any] = {}
        self.client: CoAPClient | None = None
        self._listeners: list = []
        self._task: asyncio.Task | None = None
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        # Observe frequency stats
        self._connected_at: float | None = None
        self._last_update_at: float | None = None
        self._longest_wait: float = 0.0
        self._update_intervals: list[float] = []

    async def async_start(self) -> None:
        """Load cached state, create CoAP client, and start observing."""
        self.status = await self._store.async_load() or {}
        try:
            self.client = await asyncio.wait_for(
                CoAPClient.create(self.host), timeout=15
            )
        except Exception as err:
            raise ConfigEntryNotReady(f"Cannot connect to {self.host}") from err
        self._connected_at = time.monotonic()
        self._task = asyncio.create_task(self._async_observe_status())

    async def shutdown(self) -> None:
        """Shutdown the connection."""
        if self._task:
            self._task.cancel()
        if self.client:
            try:
                await self.client.shutdown()
            except Exception as err:
                # Ignore shutdown errors (aiocoap can have race conditions during cleanup)
                _LOGGER.debug("Error during client shutdown (expected): %s", err)

    @callback
    def async_add_listener(self, update_callback) -> callable:
        """Add listener for updates."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    async def _async_observe_status(self) -> None:
        """Observe status updates from device with automatic reconnection."""
        reconnect_delay = RECONNECT_DELAY_INITIAL
        max_reconnect_delay = RECONNECT_DELAY_MAX
        
        while True:
            # Ensure we have a valid client before attempting to observe
            if self.client is None:
                try:
                    _LOGGER.info("Connecting to %s", self.host)
                    self.client = await asyncio.wait_for(
                        CoAPClient.create(self.host), timeout=30
                    )
                    _LOGGER.info("Connected to %s", self.host)
                    self._connected_at = time.monotonic()
                    self._last_update_at = None
                    self._longest_wait = 0.0
                    self._update_intervals = []
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    _LOGGER.error(
                        "Failed to connect to %s: %s. Retrying in %ds...",
                        self.host, err, reconnect_delay,
                    )
                    try:
                        await asyncio.sleep(reconnect_delay)
                    except asyncio.CancelledError:
                        raise
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                    continue

            try:
                _LOGGER.debug("Starting CoAP observe for %s", self.host)
                observe_gen = self.client.observe_status()
                try:
                    while True:
                        try:
                            status = await asyncio.wait_for(
                                observe_gen.__anext__(), timeout=WATCHDOG_TIMEOUT
                            )
                        except asyncio.TimeoutError:
                            _LOGGER.warning(
                                "No status update received from %s in %ds "
                                "(watchdog triggered), reconnecting...",
                                self.host,
                                WATCHDOG_TIMEOUT,
                            )
                            break
                        except StopAsyncIteration:
                            break
                        changes = {k: v for k, v in status.items() if self.status.get(k) != v}
                        self.status = status
                        now = time.monotonic()
                        if self._last_update_at is not None:
                            interval = now - self._last_update_at
                            self._update_intervals.append(interval)
                            self._longest_wait = max(self._longest_wait, interval)
                        self._last_update_at = now
                        avg = (
                            sum(self._update_intervals) / len(self._update_intervals)
                            if self._update_intervals else None
                        )
                        conn_age = now - self._connected_at if self._connected_at is not None else None
                        status_type = status.get(PhilipsApi.STATUS_TYPE, "unknown")
                        log = _LOGGER.info if status_type == "control" else _LOGGER.debug
                        log(
                            "Observe [%s] from %s | changed=%s conn_age=%.0fs"
                            " last_interval=%s avg_interval=%s longest_wait=%.1fs",
                            status_type,
                            self.host,
                            changes,
                            conn_age or 0,
                            f"{self._update_intervals[-1]:.1f}s" if self._update_intervals else "n/a",
                            f"{avg:.1f}s" if avg is not None else "n/a",
                            self._longest_wait,
                        )
                        reconnect_delay = RECONNECT_DELAY_INITIAL  # Reset retry delay on successful update
                        # Save status to storage for restoration after restart
                        await self._store.async_save(status)
                        for update_callback in self._listeners:
                            update_callback()
                finally:
                    await observe_gen.aclose()

                # If observe ends normally or watchdog fires, reconnect
                _LOGGER.warning("CoAP observe ended for %s, reconnecting...", self.host)

            except asyncio.CancelledError:
                _LOGGER.debug("CoAP observe cancelled for %s", self.host)
                raise

            except Exception as err:
                _LOGGER.error(
                    "Error observing status for %s: %s. Reconnecting in %ds...",
                    self.host, err, reconnect_delay,
                )

            # Wait before reconnecting
            try:
                await asyncio.sleep(reconnect_delay)
            except asyncio.CancelledError:
                raise

            # Exponential backoff for retries
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

            # Tear down the client so the top of the loop rebuilds it cleanly
            try:
                if self.client:
                    await self.client.shutdown()
            except Exception as err:
                _LOGGER.debug("Error shutting down client for %s (expected): %s", self.host, err)
            finally:
                self.client = None
                self._connected_at = None
                self._last_update_at = None
                self._longest_wait = 0.0
                self._update_intervals = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Philips Heater from a config entry."""

    host = entry.data[CONF_HOST]

    coordinator = HeaterObserveCoordinator(hass, host, entry.entry_id)

    # Coordinator owns all connection logic; raises ConfigEntryNotReady if unreachable
    await coordinator.async_start()

    # Remove entities that no longer exist (polling was removed in 1.4)
    device_id = entry.data.get("device_id", entry.entry_id)
    entity_reg = er.async_get(hass)
    for unique_id_suffix in ("update_method", "polling_interval"):
        entity_id = entity_reg.async_get_entity_id(Platform.SELECT if unique_id_suffix == "update_method" else Platform.NUMBER, DOMAIN, f"{device_id}_{unique_id_suffix}")
        if entity_id:
            entity_reg.async_remove(entity_id)
            _LOGGER.debug("Removed stale entity %s", entity_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.shutdown()
    
    return unload_ok
