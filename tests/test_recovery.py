"""Recovery regression tests using small HA substitutes; no third-party test dependencies.

Run with: python3 -m unittest discover -s tests -v
These exercise the integration code, not Home Assistant's own flow manager.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch


class AbortFlow(Exception):
    """Substitute for HA's flow-control exception."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfigFlow:
    """Only the flow declaration and result helpers needed by these tests."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__()

    def async_abort(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "abort", **kwargs}

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}


def load_integration() -> tuple[ModuleType, ModuleType, ModuleType]:
    """Import the real integration with substitutes for unavailable dependencies."""
    modules: dict[str, ModuleType] = {}

    def module(name: str, **attributes: Any) -> ModuleType:
        result = ModuleType(name)
        result.__path__ = []
        result.__dict__.update(attributes)
        modules[name] = result
        parent, _, child = name.rpartition(".")
        if parent in modules:
            setattr(modules[parent], child, result)
        return result

    module("homeassistant")
    module("homeassistant.config_entries", ConfigFlow=ConfigFlow, ConfigEntry=object)
    module("homeassistant.const", CONF_HOST="host", CONF_NAME="name",
           Platform=SimpleNamespace(CLIMATE="climate", SELECT="select", NUMBER="number", SENSOR="sensor"))
    module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    module("homeassistant.exceptions", HomeAssistantError=RuntimeError)
    module("homeassistant.data_entry_flow", AbortFlow=AbortFlow, FlowResult=dict)
    module("homeassistant.components")
    module("homeassistant.components.climate", HVACAction=Mock())
    module("homeassistant.helpers")
    module("homeassistant.helpers.storage", Store=Mock())
    module("homeassistant.helpers.entity_registry", async_get=Mock())
    module("homeassistant.helpers.service_info")
    module("homeassistant.helpers.service_info.dhcp", DhcpServiceInfo=object)
    module("homeassistant.helpers.device_registry", format_mac=lambda mac: ":".join(
        mac.replace(":", "").replace("-", "").lower()[offset:offset + 2]
        for offset in range(0, 12, 2)
    ))
    module("aioairctrl", CoAPClient=object)
    module("aioairctrl.coap")
    module("aioairctrl.coap.encryption", DigestMismatchException=type("DigestMismatchException", (Exception,), {}))
    module("voluptuous", Schema=lambda schema: schema, Required=lambda key: key)

    path = Path(__file__).resolve().parents[1] / "custom_components/philips_heater_coap"
    name = "_heater_recovery_tests"
    spec = importlib.util.spec_from_file_location(name, path / "__init__.py", submodule_search_locations=[str(path)])
    assert spec is not None and spec.loader is not None
    integration = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules | {name: integration}):
        spec.loader.exec_module(integration)
        flow_module = importlib.import_module(f"{name}.config_flow")
        constants = importlib.import_module(f"{name}.const")
    return integration, flow_module, constants


integration, config_flow, const = load_integration()


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the observed DHCP failures and delayed heater readiness."""

    def setUp(self) -> None:
        self.entries: list[SimpleNamespace] = []
        self.manager = SimpleNamespace(
            async_update_entry=Mock(side_effect=self.update_entry),
            async_reload=AsyncMock(),
        )
        self.hass = SimpleNamespace(config_entries=self.manager)
        self.flow = config_flow.PhilipsHeaterConfigFlow()
        self.flow.hass = self.hass
        self.flow.flow_id = "discovery"
        self.flow.context = {}
        self.flow.unique_id = None
        self.flow._async_current_entries = Mock(side_effect=lambda include_ignore=None: [
            entry for entry in self.entries if include_ignore is not False or entry.source != "ignore"
        ])
        self.flow.async_set_unique_id = AsyncMock(side_effect=self.set_unique_id)
        self.flow._abort_if_unique_id_configured = Mock(side_effect=self.abort_if_configured)
        self.discovery = SimpleNamespace(ip="192.168.1.69", macaddress="D0BAE446D22A", hostname="mxchip")
        self.status = {
            const.PhilipsApi.MODEL_ID: "CX3120/01",
            const.PhilipsApi.DEVICE_ID: "cx3k",
            const.PhilipsApi.NAME: "Front room",
        }

    def entry(self, host: str = "192.168.1.67", mac: str | None = "d0:ba:e4:46:d2:2a",
              device_id: str = "cx3k", unique_id: str | None = "cx3k") -> SimpleNamespace:
        result = SimpleNamespace(
            entry_id=device_id, unique_id=unique_id, source="user",
            state=SimpleNamespace(value="loaded"), options={"default_heat_preset": "low"},
            data={"host": host, "mac": mac, "device_id": device_id, "model": "CX3120/01"},
        )
        self.entries.append(result)
        return result

    def update_entry(self, entry: SimpleNamespace, **updates: Any) -> bool:
        changed = any(getattr(entry, key) != value for key, value in updates.items())
        for key, value in updates.items():
            setattr(entry, key, value)
        return changed

    async def set_unique_id(self, unique_id: str) -> SimpleNamespace | None:
        self.flow.unique_id = unique_id
        return next((entry for entry in self.entries if entry.unique_id == unique_id), None)

    def abort_if_configured(self, updates: dict[str, Any], reload_on_update: bool) -> None:
        entry = next((entry for entry in self.entries if entry.unique_id == self.flow.unique_id), None)
        if entry is not None:
            self.manager.async_update_entry(entry, data={**entry.data, **updates})
            raise AbortFlow("already_configured")

    async def test_known_mac_updates_without_coap_and_preserves_other_heater(self) -> None:
        heater = self.entry()
        other = self.entry("192.168.1.191", "68:79:c4:a7:9f:6e", "cx5k", "cx5k")
        with patch.object(config_flow, "_async_probe_status", new_callable=AsyncMock) as probe:
            with self.assertRaisesRegex(AbortFlow, "already_configured"):
                await self.flow.async_step_dhcp(self.discovery)
        probe.assert_not_awaited()
        self.assertEqual(heater.data["host"], "192.168.1.69")
        self.assertEqual(heater.unique_id, "cx3k")
        self.assertEqual(heater.options, {"default_heat_preset": "low"})
        self.assertEqual(other.data["host"], "192.168.1.191")
        self.assertEqual(self.flow.unique_id, "cx3k")
        self.flow._abort_if_unique_id_configured.assert_called_once_with(
            updates={"host": "192.168.1.69", "mac": "d0:ba:e4:46:d2:2a"}, reload_on_update=False
        )

    async def test_legacy_entry_identity_is_backfilled_before_mac_recovery(self) -> None:
        heater = self.entry(mac="D0BAE446D22A", unique_id=None)
        with patch.object(config_flow, "_async_probe_status", new_callable=AsyncMock) as probe:
            with self.assertRaises(AbortFlow):
                await self.flow.async_step_dhcp(self.discovery)
        probe.assert_not_awaited()
        self.assertEqual(heater.unique_id, "cx3k")
        self.assertEqual(heater.data["host"], "192.168.1.69")

    async def test_missing_saved_mac_falls_back_to_validated_device_identity(self) -> None:
        heater = self.entry(mac=None)
        with patch.object(config_flow, "_async_probe_status", AsyncMock(return_value=self.status)) as probe:
            with self.assertRaises(AbortFlow):
                await self.flow.async_step_dhcp(self.discovery)
        probe.assert_awaited_once()
        self.assertEqual(heater.data["mac"], "d0:ba:e4:46:d2:2a")
        self.assertEqual(heater.data["host"], "192.168.1.69")

    async def test_new_heater_retries_timeout_no_status_and_incomplete_identity(self) -> None:
        responses = [TimeoutError(), None, {const.PhilipsApi.STATUS_TYPE: "control"}, self.status]
        with patch.object(config_flow, "_async_probe_status", AsyncMock(side_effect=responses)) as probe:
            with patch.object(config_flow.asyncio, "sleep", new_callable=AsyncMock) as sleep:
                result = await self.flow.async_step_dhcp(self.discovery)
        self.assertEqual(probe.await_count, 4)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], list(const.DISCOVERY_RETRY_DELAYS[:3]))
        self.assertEqual(result["step_id"], "discovery_confirm")
        result = await self.flow.async_step_discovery_confirm({})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["host"], "192.168.1.69")
        self.assertEqual(result["data"]["device_id"], "cx3k")

    async def test_discovery_stops_after_bounded_retries(self) -> None:
        with patch.object(config_flow, "_async_probe_status", AsyncMock(side_effect=TimeoutError())) as probe:
            with patch.object(config_flow.asyncio, "sleep", new_callable=AsyncMock) as sleep:
                result = await self.flow.async_step_dhcp(self.discovery)
        self.assertEqual(probe.await_count, len(const.DISCOVERY_RETRY_DELAYS) + 1)
        self.assertEqual(sleep.await_count, len(const.DISCOVERY_RETRY_DELAYS))
        self.assertEqual(result, {"type": "abort", "reason": "not_philips_device"})
        self.assertEqual(self.entries, [])

    async def test_unsupported_model_is_rejected_without_retries(self) -> None:
        self.status[const.PhilipsApi.MODEL_ID] = "unsupported"
        with patch.object(config_flow, "_async_probe_status", AsyncMock(return_value=self.status)) as probe:
            with patch.object(config_flow.asyncio, "sleep", new_callable=AsyncMock) as sleep:
                result = await self.flow.async_step_dhcp(self.discovery)
        probe.assert_awaited_once()
        sleep.assert_not_awaited()
        self.assertEqual(result["type"], "abort")

    async def test_cancelled_discovery_does_not_probe_again(self) -> None:
        waiting = asyncio.Event()

        async def wait_for_retry(delay: float) -> None:
            waiting.set()
            await asyncio.Event().wait()

        with patch.object(config_flow, "_async_probe_status", AsyncMock(return_value=None)) as probe:
            with patch.object(config_flow.asyncio, "sleep", side_effect=wait_for_retry):
                task = asyncio.create_task(self.flow.async_step_dhcp(self.discovery))
                await asyncio.wait_for(waiting.wait(), timeout=1)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        probe.assert_awaited_once()

    async def test_manual_add_during_confirmation_does_not_duplicate_device(self) -> None:
        with patch.object(config_flow, "_async_probe_status", AsyncMock(return_value=self.status)):
            await self.flow.async_step_dhcp(self.discovery)
        self.entry()
        with self.assertRaisesRegex(AbortFlow, "already_configured"):
            await self.flow.async_step_discovery_confirm({})
        self.assertEqual(len(self.entries), 1)

    async def test_manual_rediscovery_exits_cleanly_after_address_update(self) -> None:
        heater = self.entry()
        with patch.object(config_flow, "_async_probe_status", AsyncMock(return_value=self.status)):
            with self.assertRaisesRegex(AbortFlow, "already_configured"):
                await self.flow.async_step_user({"host": "192.168.1.69"})
        self.assertEqual(heater.data["host"], "192.168.1.69")

    async def test_offline_coordinator_recovers_at_dhcp_address(self) -> None:
        heater = self.entry()
        reconnect_waiting = asyncio.Event()
        resume_reconnect = asyncio.Event()
        status_saved = asyncio.Event()
        cache = {const.PhilipsApi.MODEL_ID: "CX3120/01"}
        store = SimpleNamespace(async_load=AsyncMock(return_value=cache), async_save=AsyncMock())

        async def observe() -> Any:
            yield self.status
            await asyncio.Event().wait()

        client = SimpleNamespace(observe_status=observe, shutdown=AsyncMock())
        create = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), client])

        async def reconnect_delay(delay: float) -> None:
            reconnect_waiting.set()
            await resume_reconnect.wait()

        async def saved(status: dict[str, Any]) -> None:
            status_saved.set()

        store.async_save.side_effect = saved
        self.manager.async_get_entry = Mock(return_value=heater)
        self.hass.async_add_executor_job = AsyncMock(return_value=True)
        with patch.object(integration, "Store", return_value=store):
            coordinator = integration.HeaterObserveCoordinator(self.hass, heater.data["host"], heater.entry_id)
        with patch.object(integration, "create_coap_client", create), \
             patch.object(integration.asyncio, "sleep", side_effect=reconnect_delay), \
             patch.object(integration._LOGGER, "warning"), \
             patch.object(integration._LOGGER, "error"):
            try:
                await coordinator.async_start()
                self.assertFalse(coordinator.available)
                self.assertEqual(coordinator.status, cache)
                await asyncio.wait_for(reconnect_waiting.wait(), timeout=1)
                with self.assertRaises(AbortFlow):
                    await self.flow.async_step_dhcp(self.discovery)
                resume_reconnect.set()
                await asyncio.wait_for(status_saved.wait(), timeout=1)
                self.assertTrue(coordinator.available)
                self.assertEqual(coordinator.host, "192.168.1.69")
                self.assertEqual([call.args[0] for call in create.await_args_list],
                                 ["192.168.1.67", "192.168.1.67", "192.168.1.69"])
            finally:
                await coordinator.shutdown()
        client.shutdown.assert_awaited_once()
        self.assertIsNone(coordinator._task)

    async def test_offline_setup_loads_entities_and_registers_reload_listener(self) -> None:
        heater = self.entry()
        heater.async_on_unload = Mock()
        heater.add_update_listener = Mock(return_value=lambda: None)
        self.hass.data = {}
        self.manager.async_forward_entry_setups = AsyncMock()
        self.manager.async_unload_platforms = AsyncMock(return_value=True)
        store = SimpleNamespace(async_load=AsyncMock(return_value={}), async_save=AsyncMock())
        registry = SimpleNamespace(async_get_entity_id=Mock(return_value=None))
        with patch.object(integration, "Store", return_value=store), \
             patch.object(integration, "create_coap_client", AsyncMock(side_effect=TimeoutError())), \
             patch.object(integration.HeaterObserveCoordinator, "_async_observe_status", new_callable=AsyncMock), \
             patch.object(integration.er, "async_get", return_value=registry), \
             patch.object(integration._LOGGER, "warning"):
            try:
                self.assertTrue(await integration.async_setup_entry(self.hass, heater))
                self.manager.async_forward_entry_setups.assert_awaited_once_with(
                    heater, integration.PLATFORMS
                )
                coordinator = self.hass.data[const.DOMAIN][heater.entry_id]
                self.assertFalse(coordinator.available)
                self.assertIsNotNone(coordinator._task)
                heater.add_update_listener.assert_called_once_with(integration.async_reload_entry)
                await integration.async_reload_entry(self.hass, heater)
                self.manager.async_reload.assert_awaited_once_with(heater.entry_id)
            finally:
                await integration.async_unload_entry(self.hass, heater)
        self.assertNotIn(heater.entry_id, self.hass.data[const.DOMAIN])

    async def test_initial_status_network_failure_starts_background_recovery(self) -> None:
        store = SimpleNamespace(async_load=AsyncMock(return_value={}), async_save=AsyncMock())
        client = SimpleNamespace(shutdown=AsyncMock())
        with patch.object(integration, "Store", return_value=store):
            coordinator = integration.HeaterObserveCoordinator(self.hass, "192.168.1.69", "cx3k")
        with patch.object(integration, "create_coap_client", AsyncMock(return_value=client)), \
             patch.object(integration, "get_status_via_tickle", AsyncMock(side_effect=OSError("offline"))), \
             patch.object(coordinator, "_async_observe_status", new_callable=AsyncMock), \
             patch.object(integration._LOGGER, "warning"):
            await coordinator.async_start()
            self.assertIsNotNone(coordinator._task)
            self.assertIsNone(coordinator.client)
            self.assertFalse(coordinator.available)
            await coordinator.shutdown()
        client.shutdown.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
