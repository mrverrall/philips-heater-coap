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

### Control Fields
| Field | D-Code | Values |
|-------|--------|--------|
| POWER | D03102 | 0=OFF, 1=ON |
| OPERATING_MODE | D0310C | 0=auto, 65=high, 66=low, -127=vent |
| TARGET_TEMP | D0310E | 1-37°C (used in auto mode) |
| OSCILLATION | D0320F | 0=OFF, 17222=ON command, 17920=ON status |
| CHILD_LOCK | D03106 | 0=OFF, 1=ON |
| DISPLAY_BACKLIGHT | D03105 | 0-100% |

### Sensor Fields
| Field | D-Code | Values |
|-------|--------|--------|
| TEMPERATURE | D03224 | Current temp (value ÷ 10) |
| HEATING_STATUS | D0313F | 0=not heating, 65=high, 66=low, 67=medium (CX3xxx only), -16=idle |
| FAN_SPEED | D0310D | Unknown (constant at 2, function unclear) |

## Operating Modes

### HVAC Modes
| Mode | OPERATING_MODE (D0310C) | POWER |
|------|------------------------|-------|
| OFF | Any | 0 |
| AUTO | 0 | 1 |
| HEAT (High) | 65 | 1 |
| HEAT (Medium) | 67 | 1 | CX3xxx series only |
| HEAT (Low) | 66 | 1 |
| FAN_ONLY | -127 | 1 |

### Mode Detection Logic
```python
if POWER == 0:
    return OFF
elif OPERATING_MODE == 0 or HEATING_STATUS == -16:
    return AUTO
elif OPERATING_MODE == -127 or (HEATING_STATUS == 0 and OPERATING_MODE != 0):
    return FAN_ONLY
else:
    return HEAT  # OPERATING_MODE = 65 or 66
```

### HVAC Action (HEATING_STATUS)
| Value | Action | Description |
|-------|--------|-------------|
| 0 | FAN | Not heating (fan only) |
| 65 | HEATING | High intensity |
| 66 | HEATING | Low intensity |
| 67 | HEATING | Medium (auto mode) |
| -16 | IDLE | Auto target reached, idle |