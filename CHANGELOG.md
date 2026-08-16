# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Active connection monitoring**: After an idle period, the integration now uses a functionless device field to request a status update. Unanswered requests trigger reconnection with shorter exponential backoff, and reconnects pick up DHCP-discovered IP address changes.
- **Documentation**: Improved setup and troubleshooting guidance, updated discovered protocol mappings, and documented Philips app controls intentionally omitted from the integration.

### Fixed
- **Offline availability**: Climate and dynamic sensor entities now become unavailable when the heater stops responding or rejects a command, and recover when communication resumes.
- **Malformed status updates**: Undecodable device responses now preserve the last valid state, count as proof that the heater is available, and restart the observe stream instead of causing repeated full reconnects.
- **Manual setup validation**: Devices added by IP or MAC must now report a complete identity for a supported CX3120 or CX5120 heater, matching automatic discovery validation.
- **Concurrent CoAP client creation**: Client creation is serialized while the integration temporarily overrides aiocoap's process-wide transport defaults, preventing overlapping setup attempts from interfering with other clients.

## [1.8] - 2026-08-09

### Added
- **Automatic DHCP discovery**: Home Assistant now detects Philips heaters on the network automatically using the MXChip hostname broadcast and seven known MAC OUI prefixes. A notification appears when a new device is found; no IP hunting required.
- **MAC address entry**: The setup form accepts either an IP or a MAC address. Entering a MAC resolves the current IP from the ARP cache, useful when you know the MAC from the Philips app or your router before the device is added.
- **Automatic IP tracking**: DHCP broadcasts are monitored continuously; if the heater gets a new IP the stored address is updated in the background without any user action.
- **IP Address and MAC Address diagnostic sensors**: Both values are now visible on the device card under the diagnostics section.

### Changed
- Device discovery no longer registers the MAC address in the device registry, avoiding conflicts with network scanning integrations such as `nmap_tracker`. IP tracking is handled entirely by the DHCP manifest matchers.

## [1.7] - 2026-08-03

### Added
- **Model-specific config system**: `BASE_MODEL_CONFIG` defines defaults; `MODEL_CONFIGS` maps series prefixes (e.g. `CX3`, `CX5`) to sparse overrides merged at startup via `get_model_config()`. Adding support for a new model variant requires only a new entry in `MODEL_CONFIGS`.
- **CX3 oscillation fix**: CX3-series heaters (e.g. CX3120) now send the correct oscillation command value (`45` on/off) instead of the CX5 value (`17222`), which was silently ignored by the device.
- **Blocking I/O warning fixed**: CoAP client creation is now restricted to UDP transport, preventing aiocoap's TLS transport from calling `ssl.create_default_context()` (and triggering a blocking filesystem scan) on startup.
- **Reliable model detection**: Integration now fetches a full device state snapshot synchronously during startup (before the background observe task begins), ensuring `MODEL_ID` is available for config resolution even on first install.
- **Model persisted to config entry**: Once resolved from live status, the model ID is written back to `entry.data` so future restarts can resolve the correct config without waiting for the device.

## [1.6] - 2026-05-18

### Added
- **Medium heat preset** for CX3000-series heaters (operating mode `67`). Medium is automatically hidden for CX5000-series models which don't support it.

### Changed
- Releases now distributed as a zip asset so HACS installs from the release rather than cloning the repo directly.

## [1.5] - 2026-03-16

### Fixed
- Config flow now primes observe with a one-time backlight tickle (`D03105`) and restores the original value after the first status push.
- Prevents setup stalls and false `cannot_connect` when no state change occurs; this was often masked while the phone app was open because app activity generated updates.

## [1.4] - 2026-03-13

### Breaking Changes
- **Polling mode removed.** The integration now exclusively uses CoAP observe, and the **Update Method** and **Polling Interval** configuration entities are removed on next restart.

### Changed
- **Connection lifecycle improved.** `HeaterObserveCoordinator` now fully owns client creation, cached state restoration, and observe startup through a new `async_start()` method rather than setup-time orchestration.
- **Watchdog timeout increased substantially** from 120s to 24 hours (86400s) to avoid unnecessary reconnect churn during long quiet periods.
- Observe task now runs for the full coordinator lifetime rather than starting/stopping with entity listener registration.
- Polling code path removed after discovering it was fundamentally broken: `get_status()` opened its own observe connection without properly closing it, causing resource leaks and connection instability.
- Reconnect retry delay increased from 5s initial / 5min max to 30s initial / 1h max.

### Added
- Observe update logging now differentiates between `control` (user action) and `status` (periodic heartbeat) update types — control updates are logged at INFO, heartbeat pings at DEBUG
- Each observe update log includes a diff of only the fields that changed since the last update
- Observe frequency statistics logged on every update: connection age, last interval, rolling average interval, and longest wait — to characterise normal device behaviour

## [1.3] - 2026-03-01

### Added
- **CoAP Observe Watchdog**: 120s timeout to detect and recover from stale observe connections

### Changed
- Default polling interval increased from 10s to 20s to match the device's observe push cadence
- Auto+ preset is now selectable from the HA preset list and always applies the configured offset from current room temperature when chosen (device state reports back as Auto, which accurately reflects the device's mode)

### Fixed
- Auto+ preset was not appearing in the HA preset selector
- Selecting Auto+ when already in Auto mode did not apply the temperature offset

## [1.2] - 2026-02-14

### Added
- **Advanced Preset Modes**: New Auto, Fan, and Auto+ presets alongside existing Low and High
- **Auto+ Preset**: Automatic temperature control with configurable offset (1-10°C) above current room temperature
- **Default Heat Preset Configuration**: Select entity to set which preset is used when switching to heat mode (useful for Matterbridge and other integrations that only support basic HVAC modes)
- **Auto+ Temperature Offset Configuration**: Number entity to configure the temperature offset for Auto+ preset

### Changed
- Integration display name simplified from "Philips Heater (CoAP)" to "Philips Heater" in UI
- Preset modes now work across all HVAC modes, not just Heat mode

### Fixed
- Heating Mode diagnostic sensor now correctly shows "Off" when device is powered off (previously showed last operating mode)
- Target Temperature diagnostic sensor now returns unavailable when device is off (previously showed stale value)

## [1.1] - 2026-01-14

### Added
- **Heating Intensity Sensor**: Reports current heating status (Not Heating, Low, Medium, High)
- **Heating Mode Sensor**: Shows current operating mode (Auto, High, Low, Fan)
- **Target Temperature Sensor**: Displays the setpoint temperature

### Changed
- Code refactoring: Simplified device value mapping with centralized constants (`OPERATING_MODE_MAP`, `HEATING_INTENSITY_MAP`)
- Documentation: Clarified focus on Philips heaters in README

### Fixed
- Fixed undefined variable reference in heating intensity sensor

### Technical
- Updated climate and sensor logic to use shared mapping constants from `const.py`
- Cleaned up unused files from repository

## [1.0] - Initial Release

### Added
- Full climate entity support with HVAC modes (Off, Heat, Auto, Fan Only)
- Preset modes for heating intensity (Low, High)
- Temperature control and monitoring
- Oscillation (swing mode) control
- Real-time updates via CoAP observe protocol with automatic reconnection
- Polling mode fallback with configurable interval
- Configuration flow for easy device setup
- Update method selection (observe/polling) via select entity
- Polling interval configuration via number entity
- Support for Philips CX3120 and CX5120 heaters
- Local network communication only (no cloud required)
