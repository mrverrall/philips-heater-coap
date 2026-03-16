"""Config flow for Philips Heater integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioairctrl import CoAPClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, PhilipsApi

_LOGGER = logging.getLogger(__name__)

_BACKLIGHT_FIELD = "D03105"  # display backlight (0=off, 1=on)


async def _get_status_via_tickle(client: CoAPClient) -> dict | None:
    """Get device status using the observe + brightness-tickle pattern.

    The device only pushes status notifications when state changes, so we
    alternate the display backlight between 0 and 1 to force a push.
    We start with 0 (off) because 1 (on) is the most common resting state,
    making the first attempt the most likely to trigger a change.
    Once a status update arrives we restore the backlight to its original value.
    """
    for write_value in (0, 1):
        # Fresh generator each attempt — a cancelled __anext__() leaves the
        # generator in a broken state and subsequent calls raise StopAsyncIteration.
        observe_gen = client.observe_status()
        try:
            # Start the observe GET as a background task BEFORE sending the
            # write, so the CoAP observe registration is in-flight when the
            # device processes the write and decides to push a notification.
            anext_task = asyncio.create_task(observe_gen.__anext__())
            await asyncio.sleep(0.2)  # yield so the GET packet is dispatched

            _LOGGER.debug(
                "config_flow tickle: writing %s=%d", _BACKLIGHT_FIELD, write_value
            )
            await client.set_control_value(_BACKLIGHT_FIELD, write_value)

            try:
                status = await asyncio.wait_for(anext_task, timeout=5)
            except (asyncio.TimeoutError, StopAsyncIteration):
                # TimeoutError: device didn't respond — try the other value.
                # StopAsyncIteration: observe stream ended unexpectedly.
                anext_task.cancel()
                await asyncio.gather(anext_task, return_exceptions=True)
                continue

            # Got status — restore backlight to its original state.
            original_value = 1 - write_value
            _LOGGER.debug(
                "config_flow tickle: restoring %s=%d", _BACKLIGHT_FIELD, original_value
            )
            await client.set_control_value(_BACKLIGHT_FIELD, original_value)
            return status
        finally:
            await observe_gen.aclose()

    _LOGGER.warning("config_flow tickle: no status received after two attempts")
    return None


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
                _LOGGER.debug("Connecting to device at %s", host)
                client = await asyncio.wait_for(
                    CoAPClient.create(host), timeout=30
                )

                try:
                    _LOGGER.debug("Retrieving device status from %s via tickle", host)
                    status = await _get_status_via_tickle(client)
                finally:
                    await client.shutdown()

                if status is None:
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.debug("Successfully got status from %s", host)

                    model     = status.get(PhilipsApi.MODEL_ID, "Unknown")
                    name      = status.get(PhilipsApi.NAME, f"Philips Heater {host}")
                    device_id = status.get(PhilipsApi.DEVICE_ID, host)

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
