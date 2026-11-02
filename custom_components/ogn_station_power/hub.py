"""Hält die Verbindung zum OGN-Server und die zuletzt empfangenen Werte."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .client import OgnStatusClient
from .const import (
    APRS_LOGIN,
    CONF_CALLSIGN,
    CONF_PORT,
    CONF_SERVER,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT_MIN,
    DOMAIN,
)
from .parser import StatusPacket

_LOGGER = logging.getLogger(__name__)

# Diese Werte werden nie als "nicht verfügbar" markiert, solange sie einmal empfangen wurden.
NON_EXPIRING = {"last_update", "version"}


@dataclass(frozen=True)
class Reading:
    """Ein empfangener Wert mit Empfangszeit."""

    value: Any
    time: datetime


class OgnStationHub:
    """Eine Station: Verbindung, letzte Werte und Benachrichtigung der Sensoren."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.callsign: str = entry.data[CONF_CALLSIGN]
        self.values: dict[str, Reading] = {}
        self.connected = False
        self.signal = f"{DOMAIN}_{entry.entry_id}_update"
        self._client = OgnStatusClient(
            server=entry.data[CONF_SERVER],
            port=entry.data[CONF_PORT],
            callsign=self.callsign,
            login=APRS_LOGIN,
            on_status=self._on_status,
            on_connection=self._on_connection,
        )

    @property
    def timeout(self) -> timedelta:
        minutes = self.entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT_MIN)
        return timedelta(minutes=minutes)

    def start(self) -> None:
        """Startet die Verbindung als Hintergrundaufgabe (wird beim Entladen beendet)."""
        self.entry.async_create_background_task(
            self.hass, self._client.run(), f"{DOMAIN} {self.callsign}"
        )
        # Verfügbarkeit regelmäßig neu bewerten, auch wenn keine Pakete kommen
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1))
        )

    def is_available(self, key: str) -> bool:
        reading = self.values.get(key)
        if reading is None:
            return False
        if key in NON_EXPIRING:
            return True
        return dt_util.utcnow() - reading.time <= self.timeout

    @callback
    def _on_status(self, packet: StatusPacket) -> None:
        now = dt_util.utcnow()
        for key, value in packet.values.items():
            self.values[key] = Reading(value, now)
        if packet.version is not None:
            self.values["version"] = Reading(packet.version, now)
        if packet.uptime_min is not None:
            self.values["uptime"] = Reading(packet.uptime_min, now)
        self.values["last_update"] = Reading(now, now)
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def _on_connection(self, connected: bool) -> None:
        if connected != self.connected:
            self.connected = connected
            _LOGGER.debug("Verbindung zum OGN-Server: %s", "ok" if connected else "getrennt")

    @callback
    def _async_tick(self, _now: datetime) -> None:
        async_dispatcher_send(self.hass, self.signal)
