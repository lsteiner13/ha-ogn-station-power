"""Einrichtungsdialog und Optionen."""
from __future__ import annotations

import asyncio
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_CALLSIGN,
    CONF_PORT,
    CONF_SERVER,
    CONF_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_SERVER,
    DEFAULT_TIMEOUT_MIN,
    DOMAIN,
    MAX_TIMEOUT_MIN,
    MIN_TIMEOUT_MIN,
)

# Der Name wird in den APRS-Filter eingesetzt: nur harmlose Zeichen zulassen.
CALLSIGN_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")


async def _async_test_connection(server: str, port: int) -> None:
    """Prüft nur, ob der Server erreichbar ist."""
    async with asyncio.timeout(10):
        _reader, writer = await asyncio.open_connection(server, port)
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass


class OgnStationPowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Dialog zum Hinzufügen einer Station."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            callsign = user_input[CONF_CALLSIGN].strip()
            server = user_input[CONF_SERVER].strip()
            port = user_input[CONF_PORT]

            if not CALLSIGN_RE.match(callsign):
                errors[CONF_CALLSIGN] = "invalid_callsign"
            else:
                await self.async_set_unique_id(callsign.lower())
                self._abort_if_unique_id_configured()
                try:
                    await _async_test_connection(server, port)
                except (OSError, TimeoutError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=callsign,
                        data={CONF_CALLSIGN: callsign, CONF_SERVER: server, CONF_PORT: port},
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_CALLSIGN, default=(user_input or {}).get(CONF_CALLSIGN, "")): str,
                vol.Required(CONF_SERVER, default=(user_input or {}).get(CONF_SERVER, DEFAULT_SERVER)): str,
                vol.Required(CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OgnStationPowerOptionsFlow:
        return OgnStationPowerOptionsFlow()


class OgnStationPowerOptionsFlow(OptionsFlow):
    """Optionen: nach wie vielen Minuten ohne Status die Werte 'nicht verfügbar' werden."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT_MIN),
                ): vol.All(int, vol.Range(min=MIN_TIMEOUT_MIN, max=MAX_TIMEOUT_MIN)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
