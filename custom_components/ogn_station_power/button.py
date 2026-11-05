"""Button zum Zurücksetzen der Energie."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OgnConfigEntry
from .const import DOMAIN

RESET_DESCRIPTION = ButtonEntityDescription(key="reset_energy", translation_key="reset_energy")


async def async_setup_entry(
    hass: HomeAssistant, entry: OgnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([OgnResetEnergyButton(entry)])


class OgnResetEnergyButton(ButtonEntity):
    """Setzt den Energie-Zähler der Station auf 0 Wh."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: OgnConfigEntry) -> None:
        self.entity_description = RESET_DESCRIPTION
        self._hub = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{RESET_DESCRIPTION.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_press(self) -> None:
        async_dispatcher_send(self.hass, f"{self._hub.signal}_reset")
