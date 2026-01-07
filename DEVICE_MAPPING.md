# Philips Heater CoAP Device Mapping

This document describes the CoAP field mappings discovered through testing with a Philips CX5120/11 heater.

## Device Protocol
- **Protocol**: CoAP encrypted
- **Tested Models**: CX5120/11, should work with CX3120, AMF765, AMF870
- **Port**: UDP 5683

## CoAP Field Mappings

### Device Information
| Field | D-Code | Description | Example Value |
|-------|--------|-------------|---------------|
| NAME | D01S03 | Device name | "Garage" |
| TYPE | D01S04 | Product type | "Apollo" |
| MODEL_ID | D01S05 | Model identifier | "CX5120/11" |
| SOFTWARE_VERSION | D01S12 | Firmware version | "0.4.9" |
| DEVICE_ID | DeviceId | Unique device ID | (UUID) |

### Control Fields
| Field | D-Code | Description | Values |
|-------|--------|-------------|--------|
| POWER | D03102 | Power state | 0=OFF, 1=ON |
| MODE | D0310A | Operating mode | 1=fan, 2=circulation, 3=heating |
| HEATING_INTENSITY | D0310C | Heating level/intensity | 0=auto, 65=high, 66=low, -127=fan only |
| FAN_SPEED | D0310D | Fan speed setting | 0-3 (device specific) |
| TARGET_TEMP | D0310E | Target temperature | 1-37°C |
| CHILD_LOCK | D03106 | Child lock state | 0=OFF, 1=ON |
| DISPLAY_BACKLIGHT | D03105 | Display brightness | 0-100% |
| OSCILLATION | D0320F | Oscillation state | 0=OFF, 17222=command ON, 17920=status ON |
| TIMER | D03180 | Timer setting | 0=OFF, N=minutes |

### Sensor Fields
| Field | D-Code | Description | Format |
|-------|--------|-------------|--------|
| TEMPERATURE | D03224 | Current temperature | Value * 10 (e.g., 40 = 4.0°C) |
| HEATING_STATUS | D0313F | Current heating action | 0=fan, 65/66/67=heating, -16=idle |

## Preset Mode Mappings

### Home Assistant Presets → Device Commands
| Preset | MODE (D0310A) | HEATING_INTENSITY (D0310C) | Description |
|--------|---------------|----------------------------|-------------|
| Auto | 3 (heating) | 0 | Automatic temperature control |
| Low | 3 (heating) | 66 | Low heating power |
| Medium | 3 (heating) | 66 | Same as low (not all devices have distinct medium) |
| High | 3 (heating) | 65 | High heating power |
| Ventilation | 1 (fan) | -127 | Fan only mode |

## HVAC Mode Logic

The HVAC mode is determined by combining MODE (D0310A) and HEATING_INTENSITY (D0310C):

```python
if MODE == 3 (heating):
    if HEATING_INTENSITY == 0:
        HVAC_MODE = AUTO  # Auto temperature control
    else:
        HVAC_MODE = HEAT  # Manual heating
elif MODE == 1 or MODE == 2:
    HVAC_MODE = FAN_ONLY  # Fan or circulation mode
```

## HVAC Action Mapping

HEATING_STATUS (D0313F) indicates current activity:

| Value | HVAC Action | Description |
|-------|-------------|-------------|
| 0 | FAN | Fan running, no heating |
| 65 | HEATING | Strong/high heating active |
| 66 | HEATING | Low heating active |
| 67 | HEATING | Medium heating active |
| -16 | IDLE | Auto mode reached target, idle |

## Oscillation Behavior

The oscillation field (D0320F) has asymmetric command/status values:
- **Command to turn ON**: Send `17222`
- **Status when ON**: Device reports `17920`
- **Command to turn OFF**: Send `0`
- **Status when OFF**: Device reports `0`

Therefore, the integration checks for both `17222` and `17920` to determine if oscillation is active.

## Connection Characteristics

### Initial Discovery
- First connection can be slow (10-30 seconds)
- Timeouts set to 30s for client creation, 45s for status retrieval

### Update Methods
1. **Observe (Push)**: Default, device pushes updates via CoAP observe
   - Automatic reconnection with exponential backoff (5s → 300s)
   - Preferred method for real-time updates

2. **Polling**: Fallback method, periodic status requests
   - Configurable interval (5-300 seconds)
   - Reconnects after 3 consecutive failures

## Testing

Use the included `debug_heater_test.py` script to verify device connectivity:

```bash
python debug_heater_test.py <IP_ADDRESS>
```

This will test:
1. CoAP client creation
2. Status retrieval
3. Device information extraction
4. Observe functionality

## Notes

- All heaters tested use the same CoAP protocol schema
- Temperature values are transmitted as integers multiplied by 10
- Device responds faster to subsequent connections after initial handshake
- CoAP observe can drop connection; automatic reconnection is essential
