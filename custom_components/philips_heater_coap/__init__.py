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
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.storage import Store
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN, PhilipsApi, get_model_config
from .helpers import (
    MALFORMED_STATUS_ERRORS,
    check_network_reachable,
    create_coap_client,
    get_status_via_tickle,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.NUMBER, Platform.SENSOR]
STORAGE_VERSION = 1
STORAGE_KEY = "philips_heater_coap"
IDLE_TICKLE_AFTER = 45  # seconds without any update before nudging the device with a tickle
TICKLE_RESPONSE_TIMEOUT = 15  # seconds to wait for each tickle attempt's response
TICKLE_RETRY_ROUNDS = 3  # full 0/1 passes before giving up (NON-confirmable UDP can just drop a packet)
RECONNECT_DELAY_INITIAL = 5  # seconds before first reconnect attempt
RECONNECT_DELAY_MAX = 60  # cap backoff at one minute, this is lightweight enough to retry often


class HeaterObserveCoordinator:
    """Coordinator for Philips Heater using CoAP observe (push updates)."""

    def __init__(self, hass: HomeAssistant, host: str, entry_id: str) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.host = host
        self.entry_id = entry_id
        self.status: dict[str, Any] = {}
        self.client: CoAPClient | None = None
        self.available = False
        self._listeners: list = []
        self._task: asyncio.Task | None = None
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        # Observe frequency stats
        self._connected_at: float | None = None
        self._last_update_at: float | None = None
        self._longest_wait: float = 0.0
        self._update_intervals: list[float] = []
        self.model_config: dict = {}

    async def async_start(self) -> None:
        """Load cached state, create CoAP client, and start observing."""
        self.status = await self._store.async_load() or {}
        try:
            self.client = await asyncio.wait_for(
                    create_coap_client(self.host), timeout=15
                )
        except Exception as err:
            raise ConfigEntryNotReady(f"Cannot connect to {self.host}") from err

        # Pull the first observe response synchronously so model information is
        # available before entities are created.
        try:
            initial_status = await get_status_via_tickle(self.client, timeout=10.0)
        except MALFORMED_STATUS_ERRORS as err:
            # The payload is unusable, but receiving it proves the device is online.
            self.available = True
            _LOGGER.warning(
                "Received malformed initial status from %s (%s: %s); using cache",
                self.host,
                type(err).__name__,
                err,
            )
        else:
            if initial_status:
                self.status.update(initial_status)
                self.available = True
                await self._store.async_save(self.status)
            else:
                _LOGGER.debug("Could not get initial status, using cache")

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

    @callback
    def _async_set_available(self, available: bool) -> None:
        """Update availability and notify listeners when it changes."""
        if self.available == available:
            return

        self.available = available
        for update_callback in tuple(self._listeners):
            update_callback()

    async def async_set_control_values(self, values: dict[str, Any]) -> None:
        """Write control values when the heater is connected."""
        client = self.client
        if not self.available or client is None:
            raise HomeAssistantError(f"Philips heater at {self.host} is unavailable")

        try:
            success = await client.set_control_values(values)
        except Exception as err:
            self._async_set_available(False)
            raise HomeAssistantError(
                f"Failed to communicate with Philips heater at {self.host}"
            ) from err

        if success is False:
            self._async_set_available(False)
            raise HomeAssistantError(
                f"Philips heater at {self.host} rejected the command"
            )

    async def _async_observe_status(self) -> None:
        """Observe status updates from device with automatic reconnection."""
        reconnect_delay = RECONNECT_DELAY_INITIAL
        max_reconnect_delay = RECONNECT_DELAY_MAX

        while True:
            # Ensure we have a valid client before attempting to observe
            if self.client is None:
                # DHCP discovery may have updated the config entry's host while we
                # were down; pick up any change instead of hammering a dead IP.
                current_entry = self.hass.config_entries.async_get_entry(self.entry_id)
                if current_entry and current_entry.data.get(CONF_HOST) and current_entry.data[CONF_HOST] != self.host:
                    _LOGGER.info(
                        "Host for %s changed to %s, using updated address",
                        self.host, current_entry.data[CONF_HOST],
                    )
                    self.host = current_entry.data[CONF_HOST]
                try:
                    _LOGGER.info("Connecting to %s", self.host)
                    self.client = await asyncio.wait_for(
                        create_coap_client(self.host), timeout=30
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
                    reachable = await self.hass.async_add_executor_job(check_network_reachable, self.host)
                    if not reachable:
                        _LOGGER.warning("%s appears unreachable at the network level (routing/ARP failure)", self.host)
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
                                observe_gen.__anext__(), timeout=IDLE_TICKLE_AFTER
                            )
                        except asyncio.TimeoutError:
                            # A control write ends the device's active observe, so close ours first
                            _LOGGER.debug(
                                "No update from %s in %ds, sending tickle", self.host, IDLE_TICKLE_AFTER
                            )
                            await observe_gen.aclose()
                            try:
                                status = await get_status_via_tickle(
                                    self.client,
                                    timeout=TICKLE_RESPONSE_TIMEOUT,
                                    rounds=TICKLE_RETRY_ROUNDS,
                                )
                            except MALFORMED_STATUS_ERRORS as err:
                                # A malformed tickle response still confirms liveness.
                                self._async_set_available(True)
                                _LOGGER.warning(
                                    "Received malformed tickle status from %s (%s: %s); "
                                    "restarting observe",
                                    self.host,
                                    type(err).__name__,
                                    err,
                                )
                                observe_gen = self.client.observe_status()
                                continue
                            if status is None:
                                _LOGGER.warning(
                                    "No response to tickle from %s, connection appears stale, "
                                    "reconnecting...",
                                    self.host,
                                )
                                break
                            observe_gen = self.client.observe_status()
                        except MALFORMED_STATUS_ERRORS as err:
                            # The async generator ends after a decode error, so create a
                            # fresh observe stream while preserving the last valid state.
                            self._async_set_available(True)
                            _LOGGER.warning(
                                "Received malformed observe status from %s (%s: %s); "
                                "restarting observe",
                                self.host,
                                type(err).__name__,
                                err,
                            )
                            await observe_gen.aclose()
                            observe_gen = self.client.observe_status()
                            continue
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
                        self.available = True
                        # Save status to storage for restoration after restart
                        await self._store.async_save(status)
                        for update_callback in tuple(self._listeners):
                            update_callback()
                finally:
                    await observe_gen.aclose()

                # If observe ends normally or the tickle goes unanswered, reconnect
                _LOGGER.warning("CoAP observe ended for %s, reconnecting...", self.host)

            except asyncio.CancelledError:
                _LOGGER.debug("CoAP observe cancelled for %s", self.host)
                raise

            except Exception as err:
                _LOGGER.error(
                    "Error observing status for %s: %s. Reconnecting in %ds...",
                    self.host, err, reconnect_delay,
                )

            self._async_set_available(False)

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

    # Remove entities that were exposed during development but are no longer
    # provided by the integration. Run this before connecting so cleanup does
    # not depend on the heater being reachable.
    device_id = entry.data.get("device_id", entry.entry_id)
    entity_reg = er.async_get(hass)
    stale_entities = (
        (Platform.SELECT, "update_method"),
        (Platform.NUMBER, "polling_interval"),
        (Platform.SELECT, "timer"),
        (Platform.SENSOR, "timer_remaining"),
        (Platform.SENSOR, "last_contact"),
    )
    for platform, unique_id_suffix in stale_entities:
        entity_id = entity_reg.async_get_entity_id(
            platform, DOMAIN, f"{device_id}_{unique_id_suffix}"
        )
        if entity_id:
            entity_reg.async_remove(entity_id)
            _LOGGER.debug("Removed stale entity %s", entity_id)

    coordinator = HeaterObserveCoordinator(hass, host, entry.entry_id)

    # Coordinator owns all connection logic; raises ConfigEntryNotReady if unreachable
    await coordinator.async_start()

    # Prefer MODEL_ID from the cached live status — the config-flow tickle may produce a
    # "control"-type response that omits device-info fields, storing "Unknown" in entry.data.
    model_id = coordinator.status.get(PhilipsApi.MODEL_ID) or entry.data.get("model", "")
    coordinator.model_config = get_model_config(model_id)

    # Persist the resolved model so future restarts don't need the device to re-provide it.
    if model_id and model_id != entry.data.get("model"):
        hass.config_entries.async_update_entry(entry, data={**entry.data, "model": model_id})

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Backfill unique_id for entries added before DHCP discovery support
    if entry.unique_id is None and (raw_device_id := entry.data.get("device_id")):
        hass.config_entries.async_update_entry(entry, unique_id=raw_device_id)

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
