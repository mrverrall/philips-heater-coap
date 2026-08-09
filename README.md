# Philips Heater Integration for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square&logo=home-assistant&logoColor=white)](https://github.com/hacs/integration)
[![Latest Release](https://img.shields.io/github/v/release/mrverrall/philips-heater-coap?style=flat-square)](https://github.com/mrverrall/philips-heater-coap/releases/latest)
[![License](https://img.shields.io/github/license/mrverrall/philips-heater-coap?style=flat-square)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support%20this%20project-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/mrverrall)

A Home Assistant custom component for **Philips heaters** (CX3120, CX5120) that uses CoAP for direct local control. It communicates with the heater on your LAN and does not require the Philips cloud service or mobile app. Internet access is not required.

## About This Project

This integration focuses only on Philips heaters. It came about after debugging and patching an oscillation control issue with [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap) by [@kongo09](https://github.com/kongo09), which is a broader implementation for Philips CoAP devices.

This is a hobby project maintained in spare time grown to support others. I've even bought a CX3120 just to be able to reproduce and fix issues properly. If this saves you some hassle and you'd like to say thanks, a Ko-fi goes a long way:

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/mrverrall)

**Credit**: Thanks to [@kongo09](https://github.com/kongo09) for the comprehensive multi-device implementation and to previous contributors in the lineage of Philips CoAP projects.

## Features

- 📡 **Automatic device discovery**: finds and tracks Philips heaters on your network automatically
- 🌡️ **Climate entity support**: Home Assistant climate integration with multiple HVAC modes
- 🎯 **Preset modes**: Low, High, Auto, Fan, and Auto+ with configurable temperature offset
- 🔧 **Default heat preset option**: choose the preset used when switching to heat mode (useful for Matterbridge and other integrations that only support basic HVAC modes)
- 💫 **Oscillation control**: swing mode support
- 🔥 **Heating status sensors**: heating intensity, temperatures, and operating mode tracking
- ⚡ **CoAP observe updates**: push updates when device state changes
- 🔌 **Automatic reconnection** with exponential backoff

## Supported Devices

- Philips CX3120 Series 3000i Heater
- Philips CX5120 Series 5000i Heater

## Installation

### HACS (Recommended)

Find "Philips Heater" in HACS Integrations and install it. Or use the button below to open this repository directly in HACS.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mrverrall&repository=philips-heater-coap&category=integration)


### Manual Installation

1. Download the latest release from the [releases page](https://github.com/mrverrall/philips-heater-coap/releases)
2. Extract the files and copy the `custom_components/philips_heater_coap` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Adding your heater

If Home Assistant detects your heater on the network, you'll get a notification to add it. Just confirm and you're done. The integration watches for Philips heaters broadcasting on your network and probes any match to confirm it's genuine.

If it doesn't appear automatically, go to **Settings** → **Devices & Services** → **Add Integration**, search for "Philips Heater", and enter either the heater's IP address or its MAC address (shown in the Philips app). IP changes are tracked automatically, so you don't need a static IP.

### Device settings

Once added, you can configure the heater via the entities on its device page in **Settings** → **Devices & Services**:

- **Default Heat Preset**: which preset to apply when switching to heat mode (useful for Matterbridge and other integrations that only send heat/off). Options: low, high, auto, auto+, fan.
- **Auto+ Temperature Offset**: how many degrees (1-10°C) above the current room temperature to target in Auto+ mode. For example, a 2°C offset at 18°C targets 20°C.

## Requirements

- Home Assistant 2024.1.0 or newer
- Philips CX3120 or CX5120 heater on your local network
- Network access to the heater on CoAP port (5683/UDP)

## Usage

The integration provides these entities:

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
- **IP Address**: Current IP address of the device (diagnostic)
- **MAC Address**: Hardware MAC address, if captured at setup (diagnostic)

### Configuration Entities
- **Default Heat Preset**: Control preset used when switching to heat mode
- **Auto+ Temperature Offset**: Set offset for Auto+ preset

## Troubleshooting

### Cannot Connect to Heater

1. Make sure the heater is on the same network as Home Assistant. If it's on a guest or IoT VLAN with client isolation enabled, CoAP traffic won't reach it
2. Check that UDP port 5683 is not blocked by your firewall
3. Make sure the heater is powered on and responsive
4. Try pinging the heater's IP from the Home Assistant host to rule out a network issue

### Debug Logging

Enable debug logging via the integration page.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **[@kongo09](https://github.com/kongo09)**: ongoing philips-airpurifier-coap maintenance and development
- **Previous contributors**: earlier work on Philips CoAP integrations

## Related Projects

- [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap): the full-featured integration supporting air purifiers, humidifiers, and heaters
- [aioairctrl](https://github.com/kongo09/aioairctrl): Python library for Philips air control devices

---

**Note**: This is an unofficial integration and is not affiliated with or endorsed by Philips.
