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
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import (
    DISCOVERY_CONNECT_TIMEOUT,
    DISCOVERY_RETRY_DELAYS,
    DOMAIN,
    PhilipsApi,
    SUPPORTED_MODELS,
)
from .helpers import arp_lookup_mac, arp_lookup_ip, create_coap_client, get_status_via_tickle

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")


async def _async_probe_status(host: str, connect_timeout: float) -> dict[str, Any] | None:
    """Connect to a device and return its reported status."""
    _LOGGER.debug("Discovery probe connecting: host=%s timeout=%ss", host, connect_timeout)
    client = await asyncio.wait_for(create_coap_client(host), timeout=connect_timeout)
    try:
        _LOGGER.debug("Discovery probe connected; requesting status: host=%s", host)
        status = await get_status_via_tickle(client)
        _LOGGER.debug(
            "Discovery probe status: host=%s received=%s status_type=%r "
            "model=%r device_id=%r",
            host,
            status is not None,
            status.get(PhilipsApi.STATUS_TYPE) if status else None,
            status.get(PhilipsApi.MODEL_ID) if status else None,
            status.get(PhilipsApi.DEVICE_ID) if status else None,
        )
        return status
    finally:
        await client.shutdown()


def _supported_device_details(
    status: dict[str, Any] | None, host: str
) -> tuple[str, str, str] | None:
    """Return validated name, model, and device ID for a supported heater."""
    if not status:
        _LOGGER.debug("Discovery validation rejected: host=%s no usable status", host)
        return None

    model = status.get(PhilipsApi.MODEL_ID)
    device_id = status.get(PhilipsApi.DEVICE_ID)
    if not isinstance(model, str) or not isinstance(device_id, str):
        _LOGGER.debug(
            "Discovery validation rejected: host=%s missing or invalid identity "
            "model=%r device_id=%r",
            host, model, device_id,
        )
        return None

    model = model.strip()
    device_id = device_id.strip()
    if (
        not model
        or not device_id
        or not any(supported_model in model.upper() for supported_model in SUPPORTED_MODELS)
    ):
        _LOGGER.debug(
            "Discovery validation rejected: host=%s empty identity or unsupported "
            "model=%r device_id=%r",
            host, model, device_id,
        )
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

                        await self._async_abort_if_configured(device_id, host, mac)

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

                except AbortFlow:
                    raise
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
        _LOGGER.debug(
            "DHCP discovery received: flow_id=%s ip=%s mac=%s hostname=%s",
            self.flow_id, ip, mac, discovery_info.hostname,
        )
        # A known MAC is sufficient to track an address change. DHCP can arrive
        # before CoAP is ready; the coordinator will reconnect at the new address.
        for entry in self._async_current_entries(include_ignore=False):
            saved_mac = entry.data.get("mac")
            if not saved_mac or format_mac(saved_mac) != mac:
                continue
            device_id = entry.unique_id or entry.data.get("device_id")
            if not isinstance(device_id, str) or not device_id:
                continue
            if entry.unique_id is None:
                self.hass.config_entries.async_update_entry(entry, unique_id=device_id)
            _LOGGER.debug(
                "DHCP discovery matched saved MAC before probing: entry_id=%s "
                "stored_host=%s discovered_host=%s mac=%s",
                entry.entry_id, entry.data.get(CONF_HOST), ip, mac,
            )
            await self._async_abort_if_configured(device_id, ip, mac)

        # New devices still need a supported identity. Retry transient failures
        # in this background discovery flow without delaying integration setup.
        for attempt, delay in enumerate((0, *DISCOVERY_RETRY_DELAYS), start=1):
            if delay:
                _LOGGER.debug(
                    "DHCP discovery retry scheduled: flow_id=%s ip=%s "
                    "attempt=%s delay=%ss",
                    self.flow_id, ip, attempt, delay,
                )
                await asyncio.sleep(delay)
            try:
                status = await _async_probe_status(
                    ip, connect_timeout=DISCOVERY_CONNECT_TIMEOUT
                )
            except Exception as err:
                _LOGGER.debug(
                    "DHCP discovery probe failed: flow_id=%s ip=%s mac=%s "
                    "attempt=%s error=%s: %s",
                    self.flow_id, ip, mac, attempt, type(err).__name__, err,
                    exc_info=True,
                )
                continue

            if (device_details := _supported_device_details(status, ip)) is not None:
                break

            # A reported, unsupported model is not a heater still booting.
            model = status.get(PhilipsApi.MODEL_ID) if status else None
            if isinstance(model, str) and model.strip() and not any(
                supported_model in model.upper() for supported_model in SUPPORTED_MODELS
            ):
                return self.async_abort(reason="not_philips_device")
        else:
            _LOGGER.debug(
                "DHCP discovery aborted: flow_id=%s ip=%s mac=%s "
                "reason=not_philips_device discovery retries exhausted",
                self.flow_id, ip, mac,
            )
            return self.async_abort(reason="not_philips_device")

        name, model, device_id = device_details

        _LOGGER.debug(
            "DHCP heater validated: flow_id=%s ip=%s mac=%s model=%s device_id=%s",
            self.flow_id, ip, mac, model, device_id,
        )
        await self._async_abort_if_configured(device_id, ip, mac)

        _LOGGER.debug(
            "DHCP discovery offering new heater: flow_id=%s ip=%s device_id=%s",
            self.flow_id, ip, device_id,
        )
        self._discovery_ip = ip
        self._discovery_mac = mac
        self._discovery_name = name
        self._discovery_model = model
        self._discovery_device_id = device_id
        self.context["title_placeholders"] = {"name": self._discovery_name}

        return await self.async_step_discovery_confirm()

    async def _async_abort_if_configured(
        self, device_id: str, host: str, mac: str | None = None
    ) -> None:
        """Update a configured heater's address and stop the duplicate flow."""
        existing_entry = await self.async_set_unique_id(device_id)
        if existing_entry is not None and existing_entry.data.get(CONF_HOST) != host:
            _LOGGER.info(
                "Updating heater address: entry_id=%s old_host=%s new_host=%s",
                existing_entry.entry_id, existing_entry.data.get(CONF_HOST), host,
            )
        updates = {CONF_HOST: host}
        if mac is not None:
            updates["mac"] = mac
        # The entry's update listener owns reloads; avoid scheduling two.
        self._abort_if_unique_id_configured(updates=updates, reload_on_update=False)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm adding a device found via DHCP discovery."""
        if user_input is not None:
            assert self._discovery_device_id is not None
            assert self._discovery_ip is not None
            await self._async_abort_if_configured(
                self._discovery_device_id, self._discovery_ip, self._discovery_mac
            )
            _LOGGER.debug(
                "DHCP discovery confirmed: flow_id=%s ip=%s mac=%s device_id=%s",
                self.flow_id, self._discovery_ip, self._discovery_mac,
                self._discovery_device_id,
            )
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
