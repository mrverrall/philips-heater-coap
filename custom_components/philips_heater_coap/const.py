"""Constants for Philips Heater integration."""

from homeassistant.components.climate import HVACAction

DOMAIN = "philips_heater_coap"
MANUFACTURER = "Philips"

# Supported models
SUPPORTED_MODELS = {
    "CX3120": "Philips CX3120 Heater",
    "CX5120": "Philips CX5120 Heater",
}

# Philips CoAP API keys
class PhilipsApi:
    """CoAP API field names for Philips heaters."""

    # Device information
    NAME = "D01S03"
    TYPE = "D01S04"
    MODEL_ID = "D01S05"
    SOFTWARE_VERSION = "D01S12"
    DEVICE_ID = "DeviceId"
    PRODUCT_ID = "ProductId"
    WIFI_VERSION = "WifiVersion"

    # Control
    POWER = "D03102"
    OPERATING_MODE = "D0310C"  # Primary mode control (0=auto, 65=high, 66=low, -127=vent)
    TARGET_TEMP = "D0310E"      # Target temperature (set point)
    CHILD_LOCK = "D03106"
    DISPLAY_BACKLIGHT = "D03105"
    OSCILLATION = "D0320F"
    TIMER = "D03180"
    TIMER2 = "D03182"

    # Sensors
    TEMPERATURE = "D03224"      # Current temperature
    FAN_SPEED = "D0310D"        # Unknown function (constant at 2)
    HEATING_STATUS = "D0313F"   # Heating action/intensity status (0, 65, 66, 67, -16)
    STATUS_TYPE = "StatusType"  # Update type: "control" (user action) or "status" (periodic ~20s heartbeat)


# Heating status to HVAC action mapping (maps HEATING_STATUS sensor values)
HEATING_ACTION_MAP = {
    0: HVACAction.FAN,      # Fan only
    65: HVACAction.HEATING,  # Strong heating
    66: HVACAction.HEATING,  # Low heating
    67: HVACAction.HEATING,  # Medium heating
    -16: HVACAction.IDLE,    # Auto+ reached target, idle
}

HEATING_INTENSITY_MAP = {
    -16: "Not Heating",    # Auto+ reached target, idle
    0: "Not Heating",      # Fan only
    65: "High",
    66: "Low",
    67: "Medium",  # Medium heating
}

OPERATING_MODE_MAP = {
    0: "Auto",
    65: "High",
    66: "Low",
    67: "Medium",
    -127: "Fan",
}

# Valid heating mode values (includes Off for when power is 0)
HEATING_MODE_VALUES = ["Off", "Auto", "High", "Low", "Fan"]

# Preset modes - can be used across different HVAC modes
PRESET_LOW = "low"
PRESET_MEDIUM = "medium"
PRESET_HIGH = "high"
PRESET_AUTO = "auto"
PRESET_FAN = "fan"
PRESET_AUTO_PLUS = "auto_plus"

# Models whose OPERATING_MODE does not support value 67 (medium heat).
# Any model NOT starting with one of these prefixes gets medium heat by default.
MEDIUM_HEAT_EXCLUDED_PREFIXES = {"CX5"}

PRESET_MODES = {
    PRESET_LOW: {PhilipsApi.OPERATING_MODE: 66},
    PRESET_MEDIUM: {PhilipsApi.OPERATING_MODE: 67},
    PRESET_HIGH: {PhilipsApi.OPERATING_MODE: 65},
    PRESET_AUTO: {PhilipsApi.OPERATING_MODE: 0},
    PRESET_FAN: {PhilipsApi.OPERATING_MODE: -127},
    # AUTO_PLUS is handled specially in climate.py
}

# Configuration options
CONF_DEFAULT_HEAT_PRESET = "default_heat_preset"
CONF_AUTO_PLUS_OFFSET = "auto_plus_offset"

# Default values for options
DEFAULT_HEAT_PRESET = PRESET_LOW
DEFAULT_AUTO_PLUS_OFFSET = 2

# Temperature limits
MIN_TEMP = 1
MAX_TEMP = 37
TARGET_TEMP_STEP = 1

# Oscillation
OSCILLATION_ON = 17222   # Command value to turn on
OSCILLATION_STATUS = 17920  # Status value when running
OSCILLATION_OFF = 0
