"""Constants for the EverShelf integration."""

DOMAIN = "evershelf"

# Config entry data keys
CONF_URL = "url"
CONF_TOKEN = "token"

# Options keys
CONF_EXPIRY_DAYS = "expiry_days"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CALENDAR_ATTENTION = "calendar_attention_only"

# Defaults
DEFAULT_NAME = "EverShelf"
DEFAULT_EXPIRY_DAYS = 3
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes
DEFAULT_CALENDAR_ATTENTION = False

# Options bounds
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 3600
MIN_EXPIRY_DAYS = 1
MAX_EXPIRY_DAYS = 30

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "button", "todo", "calendar", "text"]

# Fired when evershelf.generate_recipe succeeds
EVENT_RECIPE_GENERATED = "evershelf_recipe_generated"
