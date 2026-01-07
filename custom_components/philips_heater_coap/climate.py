"""Climate platform for Philips Heater."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HEATING_INTENSITY_MAP,
    MAX_TEMP,
    MIN_TEMP,
    OSCILLATION_OFF,
    OSCILLATION_ON,
    OSCILLATION_STATUS,
    PhilipsApi,
    PRESET_AUTO,
    PRESET_HIGH,
    PRESET_LOW,
    PRESET_MEDIUM,
    PRESET_MODES,
    PRESET_VENTILATION,
    TARGET_TEMP_STEP,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Philips Heater climate from config entry."""
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]
    name = entry.data.get("name", f"Philips Heater {host}")
    model = entry.data.get("model", "Unknown")
    device_id = entry.data.get("device_id", entry.entry_id)
    
    async_add_entities([PhilipsHeaterClimate(coordinator, entry, host, name, model, device_id)])


class PhilipsHeaterClimate(ClimateEntity):
    """Representation of a Philips Heater climate device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY]
    _attr_preset_modes = list(PRESET_MODES.keys())
    _attr_target_temperature_step = TARGET_TEMP_STEP
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_swing_modes = [SWING_ON, SWING_OFF]
    _attr_has_entity_name = True
    _attr_name = None  # Use device name

    def __init__(self, coordinator, entry: ConfigEntry, host: str, device_name: str, model: str, device_id: str) -> None:
        """Initialize the climate device."""
        self._coordinator = coordinator
        self._host = host
        self._model = model
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_climate"
        self._remove_listener = None
        
        # Check if using polling coordinator
        self._is_polling = hasattr(coordinator, 'async_request_refresh')
        self._attr_should_poll = self._is_polling
        
        # Get device status for version info
        status = coordinator.status
        
        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Philips",
            model=model,
            sw_version=status.get(PhilipsApi.SOFTWARE_VERSION),
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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        attrs = {
            "update_method": "polling" if self._is_polling else "observe",
            "heating_intensity": status.get(PhilipsApi.HEATING_STATUS, 0),
        }
        
        # Add fan speed if available
        if (fan_speed := status.get(PhilipsApi.FAN_SPEED)) is not None:
            attrs["fan_speed"] = fan_speed
        
        # Add mode value
        if (mode := status.get(PhilipsApi.MODE)) is not None:
            attrs["mode_value"] = mode
            
        return attrs

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        temp = status.get(PhilipsApi.TEMPERATURE)
        if temp is not None:
            return temp / 10  # Device returns temp * 10
        return None

    @property
    def target_temperature(self) -> int | None:
        """Return the target temperature."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        return status.get(PhilipsApi.TARGET_TEMP)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.is_on:
            return HVACMode.OFF
        
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        mode = status.get(PhilipsApi.MODE, 1)
        
        if mode == 3:  # Heating mode
            if self.preset_mode == PRESET_AUTO:
                return HVACMode.AUTO
            return HVACMode.HEAT
        else:  # Fan or circulation
            return HVACMode.FAN_ONLY

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if not self.is_on:
            return HVACAction.OFF
        
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        intensity = status.get(PhilipsApi.HEATING_STATUS, 0)
        return HEATING_INTENSITY_MAP.get(intensity, HVACAction.IDLE)

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        for preset, pattern in PRESET_MODES.items():
            match = all(
                status.get(k) == v
                for k, v in pattern.items()
            )
            if match:
                return preset
        return None

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        osc = status.get(PhilipsApi.OSCILLATION, 0)
        return SWING_ON if osc in (OSCILLATION_ON, OSCILLATION_STATUS) else SWING_OFF

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        status = self._coordinator.data if self._is_polling else self._coordinator.status
        return status.get(PhilipsApi.POWER) == 1

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        temp = int(temp)
        temp = max(self._attr_min_temp, min(temp, self._attr_max_temp))
        
        await self._coordinator.client.set_control_values({PhilipsApi.TARGET_TEMP: temp})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.AUTO:
            await self.async_set_preset_mode(PRESET_AUTO)
        elif hvac_mode == HVACMode.FAN_ONLY:
            await self.async_set_preset_mode(PRESET_VENTILATION)
        elif hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(PRESET_MEDIUM)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode not in PRESET_MODES:
            return
        
        await self._coordinator.client.set_control_values(PRESET_MODES[preset_mode])
        await self.async_turn_on()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        value = OSCILLATION_ON if swing_mode == SWING_ON else OSCILLATION_OFF
        await self._coordinator.client.set_control_values({PhilipsApi.OSCILLATION: value})

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self._coordinator.client.set_control_values({PhilipsApi.POWER: 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self._coordinator.client.set_control_values({PhilipsApi.POWER: 0})
