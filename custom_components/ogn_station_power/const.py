"""Konstanten der Integration OGN Station Power."""
from __future__ import annotations

DOMAIN = "ogn_station_power"

CONF_CALLSIGN = "callsign"
CONF_SERVER = "server"
CONF_PORT = "port"
CONF_TIMEOUT = "timeout"

DEFAULT_SERVER = "aprs.glidernet.org"
DEFAULT_PORT = 14580
# Die Station sendet etwa alle 5 Minuten. Danach gelten die Werte als veraltet.
DEFAULT_TIMEOUT_MIN = 30
MIN_TIMEOUT_MIN = 6
MAX_TIMEOUT_MIN = 1440

# Login-Name der read-only Verbindung zum OGN-APRS-Server
APRS_LOGIN = "HAOGN"

# Zwischen zwei Paketen darf höchstens so viel Zeit liegen, damit die Energie
# integriert wird (sonst z. B. Nachtabschaltung der Station -> keine Schätzung).
ENERGY_MAX_GAP_MIN = 15
