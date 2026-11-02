"""Parser für den APRS-Status einer breezedudeGS-Station (ohne Home-Assistant-Abhängigkeit).

Beispiel einer Statuszeile:
    MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:123min B:4.12V +0.123A P:0.51W
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STATUS_RE = re.compile(r"^(?P<call>[^>\s]+)>(?P<path>[^:]*):>(?P<time>\d{6})h\s*(?P<text>.*)$")
# Spannung: "B:4.12V" (eigenes Token) oder "+4.12V" (OGN-Standard)
VOLT_RE = re.compile(r"(?:\bB:|(?<!\S)(?=[+-]))(-?\+?\d+(?:\.\d+)?)V")
AMP_RE = re.compile(r"(?<!\S)([+-]\d+(?:\.\d+)?)A(?!\S)")
POWER_RE = re.compile(r"\bP:(-?\d+(?:\.\d+)?)W")
VERSION_RE = re.compile(r"\bBDGS:(\S+)")
UPTIME_RE = re.compile(r"\bUP:(\d+)min")


@dataclass
class StatusPacket:
    """Ein ausgewerteter Status der Station."""

    call: str
    packet_time: str  # hhmmss laut Station
    text: str
    values: dict[str, float] = field(default_factory=dict)  # voltage, current, power
    version: str | None = None
    uptime_min: int | None = None


def parse_status(line: str) -> StatusPacket | None:
    """Wertet eine APRS-Zeile aus.

    Gibt None zurück, wenn es kein Status der Station ist oder weder Messwerte
    noch eine Firmware-Version enthalten sind.
    """
    match = STATUS_RE.match(line.strip())
    if not match:
        return None
    text = match.group("text")

    values: dict[str, float] = {}
    for key, regex in (("voltage", VOLT_RE), ("current", AMP_RE), ("power", POWER_RE)):
        found = regex.search(text)
        if found:
            values[key] = float(found.group(1))

    version_match = VERSION_RE.search(text)
    uptime_match = UPTIME_RE.search(text)
    version = version_match.group(1) if version_match else None
    if not values and version is None:
        return None

    return StatusPacket(
        call=match.group("call"),
        packet_time=match.group("time"),
        text=text,
        values=values,
        version=version,
        uptime_min=int(uptime_match.group(1)) if uptime_match else None,
    )
