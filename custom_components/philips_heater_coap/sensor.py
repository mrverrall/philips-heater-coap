"""Sensor platform for Philips Heater."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PhilipsApi

_LOGGER = logging.getLogger(__name__)

# Map heating intensity values to readable states
# Only includes actual heating states; 0 (fan only) and -16 (auto idle) return None
HEATING_INTENSITY_MAP = {
    65: "High",
    66: "Low",
    67: "Medium",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Philips Heater sensors from config entry."""
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    name = entry.data.get("name", f"Philips Heater {host}")
    model = entry.data.get("model", "Unknown")
    device_id = entry.data.get("device_id", entry.entry_id)
    
    sensors = [
        PhilipsHeaterTemperatureSensor(coordinator, entry, host, name, model, device_id),
        PhilipsHeaterIntensitySensor(coordinator, entry, host, name, model, device_id),
    ]
    
    async_add_entities(sensors)


class PhilipsHeaterSensorBase(SensorEntity):
    """Base class for Philips Heater sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        model: str,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._host = host
        self._model = model
        self._device_id = device_id
        self._remove_listener = None
        
        # Check if using polling coordinator
        self._is_polling = hasattr(coordinator, 'async_request_refresh')
        self._attr_should_poll = self._is_polling
        
        # Get device status for version info
        status = coordinator.status if hasattr(coordinator, 'status') else coordinator.data
        
        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Philips",
            model=model,
            sw_version=status.get(PhilipsApi.SOFTWARE_VERSION) if status else None,
            configuration_url=f"http://{host}",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        if self._is_polling:
            # Polling coordinator - use standard CoordinatorEntity pattern
            self.async_on_remove(
                self._coordinator.async_add_listener(self._handle_coordinator_update)
            )
        else:
            # Observe coordinator - use custom listener pattern
            self._remove_listener = self._coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        """When entity is removed from hass."""
        if not self._is_polling and self._remove_listener:
            self._remove_listener()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._is_polling:
            return self._coordinator.last_update_success
        return self._coordinator.status is not None


class PhilipsHeaterTemperatureSensor(PhilipsHeaterSensorBase):
    """Temperature sensor for Philips Heater."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Temperature"

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        model: str,
        device_id: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, entry, host, device_name, model, device_id)
        self._attr_unique_id = f"{device_id}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        if status:
            temp = status.get(PhilipsApi.TEMPERATURE)
            if temp is not None:
                return round(temp / 10, 1)  # Device returns temp * 10
        return None


class PhilipsHeaterIntensitySensor(PhilipsHeaterSensorBase):
    """Heating intensity sensor for Philips Heater."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(HEATING_INTENSITY_MAP.values())
    _attr_name = "Heating Intensity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        host: str,
        device_name: str,
        model: str,
        device_id: str,
    ) -> None:
        """Initialize the heating intensity sensor."""
        super().__init__(coordinator, entry, host, device_name, model, device_id)
        self._attr_unique_id = f"{device_id}_heating_intensity"

    @property
    def native_value(self) -> str | None:
        """Return the current heating intensity."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        if status:
            intensity = status.get(PhilipsApi.HEATING_STATUS)
            if intensity is not None:
                return HEATING_INTENSITY_MAP.get(intensity, "Unknown")
        return None
