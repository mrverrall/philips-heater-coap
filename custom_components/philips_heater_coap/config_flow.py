"""Config flow for Philips Heater integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioairctrl import CoAPClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PhilipsApi

_LOGGER = logging.getLogger(__name__)


class PhilipsHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips Heater."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            
            try:
                # Try to connect to the device (can take up to 60 seconds)
                _LOGGER.debug("Connecting to device at %s", host)
                client = await asyncio.wait_for(
                    CoAPClient.create(host),
                    timeout=30
                )
                
                # Get device info (can be slow on first connection)
                _LOGGER.debug("Retrieving device status from %s", host)
                status, _ = await asyncio.wait_for(
                    client.get_status(),
                    timeout=30
                )
                
                await client.shutdown()
                _LOGGER.debug("Successfully connected to %s", host)
                
                # Extract device info
                model = status.get(PhilipsApi.MODEL_ID, "Unknown")
                name = status.get(PhilipsApi.NAME, f"Philips Heater {host}")
                device_id = status.get(PhilipsApi.DEVICE_ID, host)
                
                # Check if already configured
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_NAME: name,
                        "model": model,
                        "device_id": device_id,
                    },
                )
                
            except asyncio.TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
            }),
            errors=errors,
        )
    