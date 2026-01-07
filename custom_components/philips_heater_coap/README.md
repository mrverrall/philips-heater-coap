# Philips Heater CoAP Integration

> **For full documentation, installation instructions, and support, see the [main repository](https://github.com/mrverrall/philips-heater-coap).**

## Technical Overview

This custom component provides Home Assistant integration for Philips heaters (CX3120, CX5120) using the CoAP protocol with real-time updates via CoAP observe.

### Platforms
- **Climate**: Full heater control with temperature, presets, and oscillation

### Dependencies
- `aioairctrl==0.2.5` - Python library for Philips air control device communication

### Communication
- Protocol: CoAP (Constrained Application Protocol)
- Port: UDP 5683
- Update method: CoAP observe (push updates, not polling)

### Supported Devices
- Philips CX3120 Series 3000i Heater
- Philips CX5120 Series 5000i Heater

## Quick Setup

1. Install via HACS or copy this folder to `custom_components/`
2. Restart Home Assistant
3. Add integration via Settings → Devices & Services
4. Enter heater IP address

## Credits

This is a simplified heater-only rewrite of [philips-airpurifier-coap](https://github.com/kongo09/philips-airpurifier-coap) by [@kongo09](https://github.com/kongo09).
