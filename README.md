# OGN Station Power (breezedudeGS) for Home Assistant

Home Assistant integration that shows **voltage, current and power** of a
[breezedudeGS](https://github.com/Breezedude/breezedudeGS) FANET/OGN ground station
(with INA219 power monitor) as normal sensors.

The values are read from the public **Open Glider Network (OGN) APRS stream**: the station
sends a status line about every 5 minutes, e.g.

```
MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:123min B:4.12V +0.123A P:0.51W
```

The integration keeps a read-only connection to `aprs.glidernet.org:14580`, filters the
station by name and updates the sensors whenever a status arrives. No MQTT broker, no
add-on and no access to the station itself is needed – it works from anywhere.

## Requirements

* Home Assistant 2024.12 or newer (any installation type).
* The station must have **"Send data to APRS server"** enabled and the INA219 enabled
  (otherwise the status contains no current/power).

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/lsteiner13/ha-ogn-station-power`
   with category **Integration**.
2. Install **OGN Station Power (breezedudeGS)** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → OGN Station Power*, enter the
   **station name** exactly as set in the station (e.g. `MyGS`).

Manual installation: copy `custom_components/ogn_station_power` to `config/custom_components/`.

## Entities

| Entity | Unit | Notes |
|---|---|---|
| Voltage | V | |
| Current | A | positive = flow from `VIN+` to `VIN-` of the INA219 (charging, if the shunt is in the charge line) |
| Power | W | voltage × current as reported by the station |
| Energy (net) | Wh | integrated from the power values; positive and negative power are both counted (net energy, can decrease) |
| Reset energy (button) | – | sets the energy counter back to 0 Wh |
| Uptime, Firmware version, Last update | – | diagnostic |

Notes:

* The station reports a **smoothed 5-minute value**. Short sun/shade changes are averaged out.
  The energy sensor is therefore an approximation, good enough for daily/weekly values.
* The energy sensor does not estimate across gaps longer than 15 minutes (e.g. while the
  station sleeps at night) and keeps its value over restarts.
* If no status arrives for **30 minutes** (configurable under *Configure*), the measurement
  sensors become *unavailable*. This also happens while the station is switched off at night
  (time-based shutdown in the station's settings).
* After a restart of Home Assistant it can take up to 5 minutes until the first values appear
  (OGN does not replay old packets).

## Troubleshooting

Enable debug logging to see every received status:

```yaml
logger:
  logs:
    custom_components.ogn_station_power: debug
```

* "Cannot connect": Home Assistant cannot reach `aprs.glidernet.org:14580` (firewall/DNS).
* No values: check that the station is connected to the APRS server (station web UI → APRS: connected)
  and that the name matches. The station name is case-insensitive here.

## Development

Parser and APRS client do not depend on Home Assistant and have tests:

```
python -m unittest discover -s tests -v
```

## License

MIT, see `LICENSE`.
