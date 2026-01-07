# Philips Heater CoAP Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/mrverrall/philips-heater-coap.svg)](https://github.com/mrverrall/philips-heater-coap/releases)
[![License](https://img.shields.io/github/license/mrverrall/philips-heater-coap.svg)](LICENSE)

A Home Assistant custom component for **Philips heaters only** (CX3120, CX5120) using the CoAP protocol.

## About This Project

This integration is a **simplified rewrite** focusing exclusively on **heater functionality**. It's based on the [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap) project by [@kongo09](https://github.com/kongo09), which is the current active implementation for Philips CoAP devices. This focused rewrite provides a simpler, more maintainable codebase specifically for Philips heaters.

**Credit**: Thanks to [@kongo09](https://github.com/kongo09) for the comprehensive multi-device implementation and to previous contributors in the lineage of Philips CoAP projects.

## Features

- 🌡️ **Full climate entity support** - Complete Home Assistant climate platform integration
- 🔄 **Functional oscillation control** - Working swing mode implementation
- ⚡ **Real-time updates via CoAP observe protocol** - Instant push updates when device state changes
- 🔄 **Polling mode fallback** with configurable interval
- 🔌 **Automatic reconnection** with exponential backoff

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
8. Find "Philips Heater (CoAP)" in HACS and install it
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/mrverrall/philips-heater-coap/releases)
2. Extract the files and copy the `custom_components/philips_heater_coap` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Philips Heater (CoAP)"
4. Enter your heater's IP address
5. Click Submit

The integration will automatically discover and configure your heater.

### Device Configuration

After adding the integration, you can configure update behavior on the device page:

1. Go to **Settings** → **Devices & Services**
2. Find your Philips heater device
3. Click on the device to see configuration entities:
   - **Update Method**: Choose between "observe" (push updates) or "polling"
   - **Polling Interval**: Set update frequency when using polling mode (5-300 seconds)

**Observe mode** (default) uses CoAP observe for real-time push updates with automatic reconnection.  
**Polling mode** periodically requests status updates at the configured interval.

## Requirements

- Home Assistant 2024.1.0 or newer
- Philips CX3120 or CX5120 heater on your local network
- Network access to the heater on CoAP port (5683/UDP)

## Usage

The integration provides full climate control with:
- Multiple HVAC and preset modes
- Temperature control and monitoring
- Oscillation control
- Heating intensity sensor

## Troubleshooting

### Cannot Connect to Heater

1. Verify the heater is on the same network as Home Assistant
2. Check that UDP port 5683 is not blocked by your firewall
3. Ensure the IP address is correct and the heater is powered on
4. Try pinging the heater from the Home Assistant host

### Entity Not Updating

By default, the integration uses CoAP's observe protocol for real-time push updates. If updates are slow or unreliable:
1. Check your network stability
2. Try switching to **polling mode** in the device configuration
3. Adjust the polling interval if using polling mode
4. Restart the integration
5. Check Home Assistant logs for errors

### Debug Logging

Enable debug logging by adding to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.philips_heater_coap: debug
    aioairctrl: debug
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
