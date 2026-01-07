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
    MODE = "D0310A"             # Mode (1=fan, 2=circulation, 3=heating)
    HEATING_INTENSITY = "D0310C"  # Heating intensity (0=auto, 65=high, 66=low, -127=fan)
    FAN_SPEED = "D0310D"        # Fan speed setting
    TARGET_TEMP = "D0310E"      # Target temperature (set point)
    CHILD_LOCK = "D03106"
    DISPLAY_BACKLIGHT = "D03105"
    OSCILLATION = "D0320F"
    TIMER = "D03180"
    TIMER2 = "D03182"
    
    # Sensors
    TEMPERATURE = "D03224"      # Current temperature
    HEATING_STATUS = "D0313F"   # Heating action/intensity status (hvac_action)


# HVAC modes mapping
MODE_MAP = {
    1: "fan",           # Fan only
    2: "circulation",   # Circulation
    3: "heating",       # Heating
}

# Heating intensity to HVAC action mapping
HEATING_INTENSITY_MAP = {
    0: HVACAction.FAN,      # Fan only
    65: HVACAction.HEATING,  # Strong heating
    66: HVACAction.HEATING,  # Low heating
    67: HVACAction.HEATING,  # Medium heating
    -16: HVACAction.IDLE,    # Auto+ reached target, idle
}

# Preset modes
PRESET_AUTO = "auto"
PRESET_LOW = "low"
PRESET_MEDIUM = "medium"
PRESET_HIGH = "high"
PRESET_VENTILATION = "ventilation"

PRESET_MODES = {
    PRESET_AUTO: {PhilipsApi.MODE: 3, PhilipsApi.HEATING_INTENSITY: 0},
    PRESET_LOW: {PhilipsApi.MODE: 3, PhilipsApi.HEATING_INTENSITY: 66},
    PRESET_MEDIUM: {PhilipsApi.MODE: 3, PhilipsApi.HEATING_INTENSITY: 66},  # Same as low
    PRESET_HIGH: {PhilipsApi.MODE: 3, PhilipsApi.HEATING_INTENSITY: 65},
    PRESET_VENTILATION: {PhilipsApi.MODE: 1, PhilipsApi.HEATING_INTENSITY: -127},
}

# Temperature limits
MIN_TEMP = 1
MAX_TEMP = 37
TARGET_TEMP_STEP = 1

# Oscillation
OSCILLATION_ON = 17222   # Command value to turn on
OSCILLATION_STATUS = 17920  # Status value when running
OSCILLATION_OFF = 0
