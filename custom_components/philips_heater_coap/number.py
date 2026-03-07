"""Number platform for Philips Heater."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AUTO_PLUS_OFFSET, DEFAULT_AUTO_PLUS_OFFSET, DOMAIN

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
        AutoPlusOffsetNumber(coordinator, entry, host, name, model, device_id),
    ])


class AutoPlusOffsetNumber(NumberEntity):
    """Number entity for setting Auto+ temperature offset."""

    _attr_has_entity_name = True
    _attr_name = "Auto+ temperature offset"
    _attr_icon = "mdi:thermometer-plus"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = "°C"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    
    entity_description = EntityDescription(
        key="auto_plus_offset",
        name="Auto+ temperature offset",
        icon="mdi:thermometer-plus",
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
        self._attr_unique_id = f"{device_id}_auto_plus_offset"
        
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
        """Return the current Auto+ offset."""
        return self._entry.options.get(CONF_AUTO_PLUS_OFFSET, DEFAULT_AUTO_PLUS_OFFSET)

    async def async_set_native_value(self, value: float) -> None:
        """Update the Auto+ offset."""
        new_options = {**self._entry.options, CONF_AUTO_PLUS_OFFSET: int(value)}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

