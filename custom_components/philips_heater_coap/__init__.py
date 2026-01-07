"""Philips Heater integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aioairctrl import CoAPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.NUMBER, Platform.SENSOR]
DEFAULT_SCAN_INTERVAL = 10
STORAGE_VERSION = 1
STORAGE_KEY = "philips_heater_coap"


class HeaterObserveCoordinator:
    """Coordinator for Philips Heater using CoAP observe (push updates)."""

    def __init__(self, hass: HomeAssistant, client: CoAPClient, host: str, status: dict[str, Any], entry_id: str) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.client = client
        self.host = host
        self.status = status
        self._listeners: list = []
        self._task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")

    async def shutdown(self) -> None:
        """Shutdown the connection."""
        if self._task:
            self._task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self.client:
            try:
                await self.client.shutdown()
            except Exception as err:
                # Ignore shutdown errors (aiocoap can have race conditions during cleanup)
                _LOGGER.debug("Error during client shutdown (expected): %s", err)

    @callback
    def async_add_listener(self, update_callback) -> callable:
        """Add listener for updates."""
        start_observing = not self._listeners
        self._listeners.append(update_callback)

        if start_observing:
            self._start_observing()

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)
            if not self._listeners:
                if self._task:
                    self._task.cancel()
                    self._task = None
                if self._reconnect_task:
                    self._reconnect_task.cancel()
                    self._reconnect_task = None

        return remove_listener

    def _start_observing(self) -> None:
        """Start observing status updates."""
        if self._task is None:
            self._task = asyncio.create_task(self._async_observe_status())

    async def _async_observe_status(self) -> None:
        """Observe status updates from device with automatic reconnection."""
        retry_delay = 5  # Start with 5 seconds
        max_retry_delay = 300  # Max 5 minutes
        
        while True:
            try:
                _LOGGER.debug("Starting CoAP observe for %s", self.host)
                async for status in self.client.observe_status():
                    self.status = status
                    retry_delay = 5  # Reset retry delay on successful update
                    # Save status to storage for restoration after restart
                    await self._store.async_save(status)
                    for update_callback in self._listeners:
                        update_callback()
                
                # If observe ends normally (shouldn't happen), reconnect
                _LOGGER.warning("CoAP observe ended for %s, reconnecting...", self.host)
                
            except asyncio.CancelledError:
                _LOGGER.debug("CoAP observe cancelled for %s", self.host)
                raise
                
            except Exception as err:
                _LOGGER.error(
                    "Error observing status for %s: %s. Reconnecting in %d seconds...",
                    self.host,
                    err,
                    retry_delay,
                )
            
            # Wait before reconnecting
            try:
                await asyncio.sleep(retry_delay)
            except asyncio.CancelledError:
                raise
            
            # Exponential backoff for retries
            retry_delay = min(retry_delay * 2, max_retry_delay)
            
            # Try to recreate the client connection
            try:
                _LOGGER.info("Attempting to reconnect to %s", self.host)
                if self.client:
                    await self.client.shutdown()
                self.client = await asyncio.wait_for(
                    CoAPClient.create(self.host),
                    timeout=30
                )
                _LOGGER.info("Successfully reconnected to %s", self.host)
            except Exception as err:
                _LOGGER.error("Failed to reconnect to %s: %s", self.host, err)


class HeaterPollingCoordinator(DataUpdateCoordinator):
    """Coordinator for Philips Heater using polling."""

    def __init__(self, hass: HomeAssistant, client: CoAPClient, host: str, status: dict[str, Any], scan_interval: int, entry_id: str) -> None:
        """Initialize coordinator."""
        self.client = client
        self.host = host
        self.status = status
        self._consecutive_errors = 0
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from heater."""
        try:
            self.status, _ = await asyncio.wait_for(self.client.get_status(), timeout=30)
            self._consecutive_errors = 0  # Reset error count on success
            # Save status to storage for restoration after restart
            await self._store.async_save(self.status)
            return self.status
        except asyncio.TimeoutError as err:
            self._consecutive_errors += 1
            
            # Try to reconnect after 3 consecutive failures
            if self._consecutive_errors >= 3:
                _LOGGER.warning(
                    "Multiple timeout errors for %s, attempting to reconnect (attempt %d)",
                    self.host,
                    self._consecutive_errors,
                )
                try:
                    await self.client.shutdown()
                    self.client = await asyncio.wait_for(
                        CoAPClient.create(self.host),
                        timeout=30
                    )
                    _LOGGER.info("Successfully reconnected to %s", self.host)
                    self._consecutive_errors = 0
                except Exception as reconnect_err:
                    _LOGGER.error("Failed to reconnect to %s: %s", self.host, reconnect_err)
            
            raise UpdateFailed(f"Timeout fetching data from {self.host}") from err
            
        except Exception as err:
            self._consecutive_errors += 1
            _LOGGER.error("Error fetching data from %s: %s", self.host, err, exc_info=True)
            raise UpdateFailed(f"Error fetching data from {self.host}: {err}") from err

    async def shutdown(self) -> None:
        """Shutdown the connection."""
        if self.client:
            try:
                await self.client.shutdown()
            except Exception as err:
                # Ignore shutdown errors (aiocoap can have race conditions during cleanup)
                _LOGGER.debug("Error during client shutdown (expected): %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Philips Heater from a config entry."""
    
    host = entry.data[CONF_HOST]
    update_method = entry.options.get("update_method", "observe")
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    
    # Try to restore last known state
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
    cached_status = await store.async_load()
    
    try:
        # Create CoAP client with short timeout - don't block HA startup
        _LOGGER.debug("Creating CoAP client for %s", host)
        client = await asyncio.wait_for(
            CoAPClient.create(host),
            timeout=5
        )
        
        # Get initial status with short timeout
        _LOGGER.debug("Getting initial status from %s", host)
        status, _ = await asyncio.wait_for(
            client.get_status(),
            timeout=5
        )
        
        _LOGGER.info("Connected to Philips heater at %s using %s method", host, update_method)
        
    except asyncio.TimeoutError:
        # Don't block HA startup - let coordinator handle reconnection
        _LOGGER.warning(
            "Timeout connecting to %s during startup. "
            "Integration will retry in background.",
            host
        )
        # Create client without verification - coordinator will reconnect
        client = await CoAPClient.create(host)
        # Use cached status if available, otherwise empty dict
        status = cached_status if cached_status else {}
        if cached_status:
            _LOGGER.info("Using cached status for %s until device reconnects", host)
    except Exception as err:
        _LOGGER.error("Failed to connect to %s: %s", host, err)
        raise ConfigEntryNotReady(f"Failed to connect to {host}") from err
    
    # Create coordinator based on update method
    if update_method == "observe":
        coordinator = HeaterObserveCoordinator(hass, client, host, status, entry.entry_id)
    else:
        coordinator = HeaterPollingCoordinator(hass, client, host, status, scan_interval, entry.entry_id)
        # Don't block HA startup - let first refresh happen in background
        if status:  # Only do first refresh if we have initial status
            try:
                await asyncio.wait_for(
                    coordinator.async_config_entry_first_refresh(),
                    timeout=5
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("First refresh timed out for %s, will retry in background", host)
            except Exception as err:
                _LOGGER.warning("First refresh failed for %s: %s, will retry in background", host, err)
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Listen for options updates
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
