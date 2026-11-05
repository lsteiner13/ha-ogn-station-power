"""Sensoren der Station."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OgnConfigEntry
from .const import DOMAIN, ENERGY_MAX_GAP_MIN
from .hub import OgnStationHub

READING_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENERGY_DESCRIPTION = SensorEntityDescription(
    key="energy",
    translation_key="energy",
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    state_class=SensorStateClass.TOTAL,
    suggested_display_precision=2,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: OgnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Legt die Sensoren einer Station an."""
    hub = entry.runtime_data
    entities: list[SensorEntity] = [OgnReadingSensor(hub, entry, desc) for desc in READING_SENSORS]
    entities.append(OgnEnergySensor(hub, entry, ENERGY_DESCRIPTION))
    async_add_entities(entities)


class OgnBaseSensor(SensorEntity):
    """Gemeinsame Basis: gehört zum Gerät der Station und wird bei neuen Paketen aktualisiert."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: OgnStationHub, entry: OgnConfigEntry, description: SensorEntityDescription) -> None:
        self.entity_description = description
        self._hub = hub
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=hub.callsign,
            manufacturer="breezedudeGS",
            model="OGN FANET ground station",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, self._hub.signal, self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class OgnReadingSensor(OgnBaseSensor):
    """Ein direkt von der Station gemeldeter Wert."""

    @property
    def available(self) -> bool:
        return self._hub.is_available(self.entity_description.key)

    @property
    def native_value(self) -> Any:
        reading = self._hub.values.get(self.entity_description.key)
        return None if reading is None else reading.value


class OgnEnergySensor(OgnBaseSensor, RestoreSensor):
    """Energie in Wh, aus den gemeldeten Leistungswerten aufsummiert.

    Positive und negative Leistung werden vorzeichenrichtig verrechnet (Netto-Energie).
    Die Station meldet alle 5 Minuten einen geglätteten Mittelwert. Die Summe ist daher
    eine Näherung. Bei Lücken über ENERGY_MAX_GAP_MIN Minuten (z. B. Nachtabschaltung)
    wird nichts geschätzt.
    """

    def __init__(self, hub: OgnStationHub, entry: OgnConfigEntry, description: SensorEntityDescription) -> None:
        super().__init__(hub, entry, description)
        self._energy_wh = 0.0
        self._last_time: datetime | None = None
        self._last_power = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (data := await self.async_get_last_sensor_data()) is not None and data.native_value is not None:
            try:
                self._energy_wh = float(data.native_value)
                # Migration: frühere Versionen speicherten kWh
                if data.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
                    self._energy_wh *= 1000
            except (TypeError, ValueError):
                self._energy_wh = 0.0

        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{self._hub.signal}_reset", self._handle_reset)
        )

    @callback
    def _handle_reset(self) -> None:
        """Setzt den Zählerstand auf 0 (Button)."""
        self._energy_wh = 0.0
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return True  # Zählerstand bleibt auch ohne neue Pakete erhalten

    @property
    def native_value(self) -> float:
        return round(self._energy_wh, 3)

    @callback
    def _handle_update(self) -> None:
        reading = self._hub.values.get("power")
        if reading is not None and reading.time != self._last_time:
            if self._last_time is not None:
                gap_h = (reading.time - self._last_time).total_seconds() / 3600
                if 0 < gap_h <= ENERGY_MAX_GAP_MIN / 60:
                    mean_w = (self._last_power + reading.value) / 2
                    self._energy_wh += mean_w * gap_h
            self._last_time = reading.time
            self._last_power = reading.value
        self.async_write_ha_state()
