"""Select platform for Philips Heater."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory
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
    """Set up Philips Heater select from config entry."""
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    name = entry.data.get("name", f"Philips Heater {host}")
    model = entry.data.get("model", "Unknown")
    device_id = entry.data.get("device_id", entry.entry_id)
    
    async_add_entities([
        UpdateMethodSelect(coordinator, entry, host, name, model, device_id)
    ])


class UpdateMethodSelect(SelectEntity):
    """Select entity for choosing update method."""

    _attr_has_entity_name = True
    _attr_name = "Update method"
    _attr_icon = "mdi:update"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["observe", "polling"]
    
    entity_description = EntityDescription(
        key="update_method",
        name="Update method",
        icon="mdi:update",
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
        """Initialize the select entity."""
        self._coordinator = coordinator
        self._entry = entry
        self._host = host
        self._attr_unique_id = f"{device_id}_update_method"
        
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
    def current_option(self) -> str:
        """Return the current update method."""
        return self._entry.options.get("update_method", "observe")

    async def async_select_option(self, option: str) -> None:
        """Change the update method."""
        new_options = {**self._entry.options, "update_method": option}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        
        # Reload the integration to apply new method
        await self.hass.config_entries.async_reload(self._entry.entry_id)
