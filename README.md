# Philips Heater Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/mrverrall/philips-heater-coap.svg)](https://github.com/mrverrall/philips-heater-coap/releases)
[![License](https://img.shields.io/github/license/mrverrall/philips-heater-coap.svg)](LICENSE)

A Home Assistant custom component for **Philips heaters** (CX3120, CX5120) providing **local control** via the CoAP protocol. This integration communicates directly with your heater on your local network—no Philips cloud service or mobile app required. All control is completely local and works without internet access.

## About This Project

This integration focuses exclusively on Philips heaters, providing a simple and maintainable codebase. It's inspired by the [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap) project by [@kongo09](https://github.com/kongo09), which is a current active implementation for Philips CoAP devices.

**Credit**: Thanks to [@kongo09](https://github.com/kongo09) for the comprehensive multi-device implementation and to previous contributors in the lineage of Philips CoAP projects.

## Features

- 🌡️ **Full climate entity support** - Complete Home Assistant climate platform integration with multiple HVAC modes
- 🎯 **Advanced preset modes** - Low, High, Auto, Fan, and Auto+ with configurable temperature offset
- 🔧 **Configurable default heat preset** - Set the default preset when switching to heat mode (useful for Matterbridge and other integrations that only support basic HVAC modes)
- 💫 **Functional oscillation control** - Working swing mode implementation
- 🔥 **Heating status sensors** - Real-time heating intensity, temperatures and operating mode tracking
- ⚡ **Real-time updates via CoAP observe protocol** - Instant push updates when device state changes
- 🔌 **Automatic reconnection** with exponential backoff for reliable operation

## Supported Devices

- Philips CX3120 Series 3000i Heater
- Philips CX5120 Series 5000i Heater

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/mrverrall/philips-heater-coap`
6. Select category: "Integration"
7. Click "Add"
8. Find "Philips Heater" in HACS and install it
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/mrverrall/philips-heater-coap/releases)
2. Extract the files and copy the `custom_components/philips_heater_coap` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Philips Heater"
4. Enter your heater's IP address
5. Click Submit

The integration will automatically discover and configure your heater.

### Device Configuration

After adding the integration, configure settings via the configuration entities on the device page:

1. Go to **Settings** → **Devices & Services**
2. Find your Philips heater device
3. Click on the device to see all entities, including configuration entities:
   - **Default Heat Preset**: Choose which preset to use when switching to heat mode (low, high, auto, auto+, or fan)
   - **Auto+ Temperature Offset**: Set the temperature offset (1-10°C) above current temperature for Auto+ preset
**Default Heat Preset:**
This setting controls which preset is activated when switching to heat mode. This is particularly useful when using the heater with Matterbridge or other integrations that only support basic HVAC modes (heat/off). When these integrations switch the heater to "heat" mode, it will use your configured default preset (low, high, auto, auto+, or fan).

**Auto+ Preset:**
The Auto+ preset enables automatic temperature control with a configurable offset above the current room temperature. For example, with a 2°C offset and current temperature of 18°C, the heater will target 20°C in auto mode.

## Requirements

- Home Assistant 2024.1.0 or newer
- Philips CX3120 or CX5120 heater on your local network
- Network access to the heater on CoAP port (5683/UDP)

## Usage

The integration provides comprehensive climate control:

### Climate Entity
- **HVAC Modes**: Off, Heat, Auto, Fan Only
- **Preset Modes**: Low, High, Auto, Auto+, Fan
- **Target Temperature**: Set when in Auto or Auto+ mode
- **Oscillation**: Enable/disable swing mode
- **Current Temperature**: Real-time room temperature

### Sensors
- **Temperature**: Current room temperature
- **Heating Intensity**: Shows current heating level (Not Heating, Low, High, Medium)
- **Heating Mode**: Current operating mode (Off, Low, High, Auto, Fan)
- **Target Temperature**: Configured target temperature (when applicable)

### Configuration Entities
- **Default Heat Preset**: Control preset used when switching to heat mode
- **Auto+ Temperature Offset**: Set offset for Auto+ preset

## Troubleshooting

### Cannot Connect to Heater

1. Verify the heater is on the same network as Home Assistant
2. Check that UDP port 5683 is not blocked by your firewall
3. Ensure the IP address is correct and the heater is powered on
4. Try pinging the heater from the Home Assistant host

### Entity Not Updating

The integration uses CoAP's observe protocol for real-time push updates. If updates are slow or unreliable:
1. Check your network stability
2. Restart the integration
3. Check Home Assistant logs for errors

### Debug Logging

Enable debug logging by adding to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.philips_heater_coap: debug
```

## Development

This integration uses:
- **CoAP Protocol**: For local communication with Philips devices
- **aioairctrl**: Python library for Philips air control devices
- **Home Assistant Integration**: Climate platform

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **[@kongo09](https://github.com/kongo09)** - Ongoing philips-airpurifier-coap maintenance and development
- **Previous contributors** - All previous contributions leading here

## Related Projects

- [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap) - The full-featured integration supporting air purifiers, humidifiers, and heaters
- [aioairctrl](https://github.com/kongo09/aioairctrl) - Python library for Philips air control devices

---

**Note**: This is an unofficial integration and is not affiliated with or endorsed by Philips.
