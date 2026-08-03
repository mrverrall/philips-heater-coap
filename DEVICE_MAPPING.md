# Philips Heater CoAP Device Mapping

CoAP field mappings for Philips CX5120/11, CX3120, AMF765, AMF870 heaters.

## Protocol
- CoAP encrypted, UDP port 5683
- Temperature values: multiply by 10 (e.g., 40 = 4.0°C)

## CoAP Fields

### Device Information
| Field | D-Code | Values |
|-------|--------|--------|
| NAME | D01S03 | Device name |
| TYPE | D01S04 | Device type |
| MODEL_ID | D01S05 | Model identifier |
| SOFTWARE_VERSION | D01S12 | Firmware version |
| DEVICE_ID | DeviceId | Unique device identifier |
| PRODUCT_ID | ProductId | Product identifier |
| WIFI_VERSION | WifiVersion | WiFi module version |

### Control Fields (read/write)
| Field | D-Code | Values |
|-------|--------|--------|
| POWER | D03102 | 0=OFF, 1=ON |
| OPERATING_MODE | D0310C | 0=auto, 65=high, 66=low, 67=medium (CX3xxx only), -127=vent |
| TARGET_TEMP | D0310E | 1-37°C (used in auto mode) |
| OSCILLATION (5k)| D0320F | 0=OFF, 17222=ON command, 17920=ON status |
| OSCILLATION (3k)| D0320F | 0=OFF, 45=ON |
| CHILD_LOCK | D03106 (5k) D03106 (3k) | 0=OFF, 1=ON |
| DISPLAY_BACKLIGHT (CX5xxx only) | D03105 | 0-100% |

### Sensor Fields (read only)
| Field | D-Code | Values |
|-------|--------|--------|
| TEMPERATURE | D03224 | Current temp (value ÷ 10) |
| HEATING_STATUS | D0313F | 0=not heating, 65=high, 66=low, 67=medium (CX3xxx only), -16=idle |
| FAN_SPEED | D0310D | 0-4 low-high, locked to  |