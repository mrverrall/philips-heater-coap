"""Number platform for Philips Heater."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Philips Heater number from config entry."""
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    name = entry.data.get("name", f"Philips Heater {host}")
    model = entry.data.get("model", "Unknown")
    device_id = entry.data.get("device_id", entry.entry_id)
    
    async_add_entities([
        PollingIntervalNumber(coordinator, entry, host, name, model, device_id)
    ])


class PollingIntervalNumber(NumberEntity):
    """Number entity for setting polling interval."""

    _attr_has_entity_name = True
    _attr_name = "Polling interval"
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 5
    _attr_native_max_value = 300
    _attr_native_step = 5
    
    entity_description = EntityDescription(
        key="polling_interval",
        name="Polling interval",
        icon="mdi:timer-outline",
    )

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        model: str,
        device_id: str,
    ) -> None:
        """Initialize the number entity."""
        self._coordinator = coordinator
        self._entry = entry
        self._host = host
        self._attr_unique_id = f"{device_id}_polling_interval"
        
        # Get device status for software version
        status = coordinator.status
        from .const import PhilipsApi
        sw_version = status.get(PhilipsApi.SOFTWARE_VERSION)
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Philips",
            model=model,
            sw_version=sw_version,
            configuration_url=f"http://{host}",
        )

    @property
    def native_value(self) -> float:
        """Return the current polling interval."""
        return self._entry.options.get("scan_interval", 10)

    @property
    def available(self) -> bool:
        """Only available in polling mode."""
        return self._entry.options.get("update_method", "observe") == "polling"

    async def async_set_native_value(self, value: float) -> None:
        """Update the polling interval."""
        new_options = {**self._entry.options, "scan_interval": int(value)}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        
        # Reload the integration to apply new interval
        await self.hass.config_entries.async_reload(self._entry.entry_id)
