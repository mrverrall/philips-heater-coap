"""Config flow for Philips Heater integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, PhilipsApi, SUPPORTED_MODELS
from .helpers import arp_lookup_mac, arp_lookup_ip, create_coap_client, get_status_via_tickle

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")


async def _async_probe_status(host: str, connect_timeout: float) -> dict[str, Any] | None:
    """Connect to a device and return its reported status."""
    client = await asyncio.wait_for(create_coap_client(host), timeout=connect_timeout)
    try:
        return await get_status_via_tickle(client)
    finally:
        await client.shutdown()


def _supported_device_details(
    status: dict[str, Any] | None, host: str
) -> tuple[str, str, str] | None:
    """Return validated name, model, and device ID for a supported heater."""
    if not status:
        return None

    model = status.get(PhilipsApi.MODEL_ID)
    device_id = status.get(PhilipsApi.DEVICE_ID)
    if not isinstance(model, str) or not isinstance(device_id, str):
        return None

    model = model.strip()
    device_id = device_id.strip()
    if (
        not model
        or not device_id
        or not any(supported_model in model.upper() for supported_model in SUPPORTED_MODELS)
    ):
        return None

    name = status.get(PhilipsApi.NAME)
    if not isinstance(name, str) or not name.strip():
        name = f"Philips Heater {host}"
    else:
        name = name.strip()

    return name, model, device_id


class PhilipsHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips Heater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state used by discovery steps."""
        self._discovery_ip: str | None = None
        self._discovery_mac: str | None = None
        self._discovery_name: str | None = None
        self._discovery_model: str | None = None
        self._discovery_device_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input[CONF_HOST].strip()
            mac: str | None = None

            if _MAC_RE.match(raw):
                mac = raw.lower()
                host = await self.hass.async_add_executor_job(arp_lookup_ip, mac)
                if host is None:
                    errors["base"] = "mac_not_found"
            else:
                host = raw

            if not errors and host:
                try:
                    _LOGGER.debug("Connecting to device at %s", host)
                    status = await _async_probe_status(host, connect_timeout=30)

                    if status is None:
                        errors["base"] = "cannot_connect"
                    elif (device_details := _supported_device_details(status, host)) is None:
                        errors["base"] = "unsupported_device"
                    else:
                        name, model, device_id = device_details

                        await self.async_set_unique_id(device_id)
                        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                        if mac is None:
                            mac = await self.hass.async_add_executor_job(arp_lookup_mac, host)

                        entry_data: dict[str, Any] = {
                            CONF_HOST: host,
                            CONF_NAME: name,
                            "model": model,
                            "device_id": device_id,
                        }
                        if mac:
                            entry_data["mac"] = mac

                        return self.async_create_entry(title=name, data=entry_data)

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

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> FlowResult:
        """Handle DHCP discovery — new device or IP change on an existing entry."""
        ip = discovery_info.ip
        mac = format_mac(discovery_info.macaddress)

        # CoAP probe to confirm this is a Philips device and retrieve device_id
        try:
            status = await _async_probe_status(ip, connect_timeout=10)
        except Exception:
            return self.async_abort(reason="not_philips_device")

        if (device_details := _supported_device_details(status, ip)) is None:
            return self.async_abort(reason="not_philips_device")

        name, model, device_id = device_details

        await self.async_set_unique_id(device_id)
        # Already configured: silently update the stored IP and stop
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip})

        self._discovery_ip = ip
        self._discovery_mac = mac
        self._discovery_name = name
        self._discovery_model = model
        self._discovery_device_id = device_id
        self.context["title_placeholders"] = {"name": self._discovery_name}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm adding a device found via DHCP discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_name,
                data={
                    CONF_HOST: self._discovery_ip,
                    CONF_NAME: self._discovery_name,
                    "model": self._discovery_model,
                    "device_id": self._discovery_device_id,
                    "mac": self._discovery_mac,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovery_name,
                "model": self._discovery_model,
                "ip": self._discovery_ip,
            },
        )
