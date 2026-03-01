# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
