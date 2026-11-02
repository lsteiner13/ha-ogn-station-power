"""Asynchroner APRS-IS-Client für den OGN-Server (ohne Home-Assistant-Abhängigkeit)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

from .parser import StatusPacket, parse_status

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120  # der Server sendet etwa alle 20 s einen Kommentar; länger nichts = tot
KEEPALIVE_INTERVAL = 60
RECONNECT_MIN = 15
RECONNECT_MAX = 300


class OgnStatusClient:
    """Hält eine read-only Verbindung zum OGN-APRS-Server und meldet Status-Pakete einer Station."""

    def __init__(
        self,
        server: str,
        port: int,
        callsign: str,
        login: str,
        on_status: Callable[[StatusPacket], None],
        on_connection: Callable[[bool], None] | None = None,
    ) -> None:
        self._server = server
        self._port = port
        self._callsign = callsign
        self._login = login
        self._on_status = on_status
        self._on_connection = on_connection or (lambda _connected: None)
        self._got_data = False  # in der aktuellen Verbindung wurde etwas empfangen

    async def run(self) -> None:
        """Verbindet sich dauerhaft; bei Fehlern mit steigender Wartezeit neu. Läuft bis zum Abbruch."""
        delay = RECONNECT_MIN
        while True:
            self._got_data = False
            try:
                await self._session()
            except asyncio.CancelledError:
                raise
            except (OSError, TimeoutError, ConnectionError) as err:
                _LOGGER.warning(
                    "Verbindung zu %s:%s unterbrochen: %s. Neuer Versuch in %s s",
                    self._server,
                    self._port,
                    err or type(err).__name__,
                    delay,
                )
            finally:
                self._on_connection(False)
            if self._got_data:
                delay = RECONNECT_MIN  # die Verbindung hat funktioniert: wieder schnell versuchen
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _session(self) -> None:
        """Eine Verbindung. Endet immer mit einer Exception (Abbruch, Fehler oder Verbindungsende)."""
        _LOGGER.debug("Verbinde mit %s:%s", self._server, self._port)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._server, self._port), CONNECT_TIMEOUT
        )
        try:
            # pass -1 = read-only; "b/<call>" = nur Pakete dieser Station
            writer.write(
                f"user {self._login} pass -1 vers ha-ogn-station-power 0.1 filter b/{self._callsign}\r\n".encode()
            )
            await writer.drain()
            loop = asyncio.get_running_loop()
            last_keepalive = loop.time()

            while True:
                try:
                    raw = await asyncio.wait_for(reader.readline(), READ_TIMEOUT)
                except TimeoutError as err:
                    raise ConnectionError("keine Daten vom Server") from err
                if not raw:
                    raise ConnectionError("Server hat die Verbindung geschlossen")

                if not self._got_data:
                    self._got_data = True
                    self._on_connection(True)
                    _LOGGER.debug("Verbunden, warte auf Status von %s", self._callsign)

                now = loop.time()
                if now - last_keepalive > KEEPALIVE_INTERVAL:
                    writer.write(b"#keepalive\r\n")
                    await writer.drain()
                    last_keepalive = now

                line = raw.decode("latin-1").rstrip("\r\n")
                if not line or line.startswith("#"):
                    continue
                packet = parse_status(line)
                if packet is None or packet.call.lower() != self._callsign.lower():
                    continue
                _LOGGER.debug("Status von %s: %s", packet.call, packet.text)
                self._on_status(packet)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
