"""Constants for Philips Heater integration."""

import logging

from homeassistant.components.climate import HVACAction

_LOGGER = logging.getLogger(__name__)

DOMAIN = "philips_heater_coap"
MANUFACTURER = "Philips"

# Known OUI prefixes for the MXChip AZ3166 Wi-Fi module used in these heaters
MXCHIP_OUI_PREFIXES = (
    "04:78:63",
    "68:79:C4",
    "80:A0:36",
    "84:9D:C2",
    "88:A6:8D",
    "B0:F8:93",
    "D0:BA:E4",
)

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
    UNKNOWN1 = "D03182"  # No observed effect; used by helpers.py as the tickle/keepalive field

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
HEATING_MODE_VALUES = ["Off", "Auto", "High", "Medium", "Low", "Fan"]

# Preset modes - can be used across different HVAC modes
PRESET_LOW = "low"
PRESET_MEDIUM = "medium"
PRESET_HIGH = "high"
PRESET_AUTO = "auto"
PRESET_FAN = "fan"
PRESET_AUTO_PLUS = "auto_plus"

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
BASE_MODEL_CONFIG = {
    "oscillation_on": 17222,
    "oscillation_status": 17920,
    "oscillation_off": 0,
    "supports_medium_heat": False,
    "supports_display_backlight": True,
}

# Per-prefix overrides merged onto BASE_MODEL_CONFIG by get_model_config().
# CX5 is stated in full even though it mirrors the base — unknown models fall back to base defaults.
MODEL_CONFIGS: dict[str, dict] = {
    "CX5": {
        "oscillation_on": 17222,
        "oscillation_status": 17920,
        "oscillation_off": 0,
        "supports_medium_heat": False,
        "supports_display_backlight": True,
    },
    "CX3": {
        "oscillation_on": 45,
        "oscillation_status": 45,
        "supports_medium_heat": True,
        "supports_display_backlight": False,
    },
}

def get_model_config(model_id: str) -> dict:
    """Return merged model config for the given model ID, falling back to base defaults."""
    upper = model_id.upper()
    for prefix, overrides in MODEL_CONFIGS.items():
        if upper.startswith(prefix):
            config = {**BASE_MODEL_CONFIG, **overrides}
            _LOGGER.debug("Model %r matched prefix %r → oscillation_on=%s supports_medium_heat=%s", model_id, prefix, config["oscillation_on"], config["supports_medium_heat"])
            return config
    _LOGGER.warning(
        "Model %r not matched in MODEL_CONFIGS (checked prefixes: %s); using 5k base defaults — oscillation_on=%s",
        model_id, list(MODEL_CONFIGS.keys()), BASE_MODEL_CONFIG["oscillation_on"],
    )
    return dict(BASE_MODEL_CONFIG)
