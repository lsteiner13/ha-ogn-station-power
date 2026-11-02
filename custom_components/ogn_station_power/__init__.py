"""Integration OGN Station Power: Spannung, Strom und Leistung einer breezedudeGS-Station aus dem OGN-Stream."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .hub import OgnStationHub

PLATFORMS: list[Platform] = [Platform.SENSOR]

type OgnConfigEntry = ConfigEntry[OgnStationHub]


async def async_setup_entry(hass: HomeAssistant, entry: OgnConfigEntry) -> bool:
    """Richtet eine Station ein."""
    hub = OgnStationHub(hass, entry)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.start()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OgnConfigEntry) -> bool:
    """Entfernt eine Station. Die Hintergrundaufgabe endet automatisch."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: OgnConfigEntry) -> None:
    """Lädt die Integration neu, wenn sich die Optionen ändern."""
    await hass.config_entries.async_reload(entry.entry_id)
