"""Constants for the inverterzone integration."""

from __future__ import annotations

from datetime import time, timedelta
from typing import Final

DOMAIN: Final = "inverterzone"
MANUFACTURER: Final = "inverterzone"

# The inverterzone cloud's Home Assistant API.
BASE_URL: Final = "https://inverterzone.com/api/home"
REQUEST_TIMEOUT: Final = 20  # seconds

# Dongles report every 15 seconds, so polling faster gains nothing.
LIVE_INTERVAL: Final = timedelta(seconds=15)
# Today's energy totals. The cloud caches them for 5 minutes.
ENERGY_INTERVAL: Final = timedelta(minutes=30)
# One extra energy refresh just before local midnight, so the last part of the day is
# recorded before the "today" counters reset.
ENERGY_DAY_END: Final = time(23, 55)

CONF_TOKEN: Final = "token"
CONF_EXPIRES_AT: Final = "expires_at"
