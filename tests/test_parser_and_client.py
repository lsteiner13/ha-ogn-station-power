"""Tests für Parser und APRS-Client. Laufen ohne Home Assistant:  python -m unittest discover -s tests -v"""
import asyncio
import importlib
import pathlib
import sys
import types
import unittest

PKG_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "ogn_station_power"

# Das Paket ohne seine __init__.py laden (die braucht Home Assistant).
_pkg = types.ModuleType("ogn_under_test")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["ogn_under_test"] = _pkg
parser = importlib.import_module("ogn_under_test.parser")
client = importlib.import_module("ogn_under_test.client")


class ParserTests(unittest.TestCase):
    def test_custom_voltage_token(self):
        p = parser.parse_status(
            "MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:123min B:4.12V +0.123A P:0.51W"
        )
        self.assertEqual(p.call, "MyGS")
        self.assertEqual(p.packet_time, "101530")
        self.assertEqual(p.values, {"voltage": 4.12, "current": 0.123, "power": 0.51})
        self.assertEqual(p.version, "0.6.9")
        self.assertEqual(p.uptime_min, 123)

    def test_standard_token_and_negative_values(self):
        p = parser.parse_status(
            "MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:5min +4.12V -0.035A P:-0.14W"
        )
        self.assertEqual(p.values, {"voltage": 4.12, "current": -0.035, "power": -0.14})

    def test_only_voltage(self):
        p = parser.parse_status("MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:5min B:3.98V")
        self.assertEqual(p.values, {"voltage": 3.98})

    def test_sleep_note_does_not_confuse(self):
        p = parser.parse_status(
            "MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:5min B:4.12V +3.200A P:13.18W SLEEP:22:00-06:00 480min"
        )
        self.assertEqual(p.values, {"voltage": 4.12, "current": 3.2, "power": 13.18})

    def test_version_only_is_accepted(self):
        p = parser.parse_status("MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:>101530h BDGS:0.6.9 UP:5min")
        self.assertEqual(p.values, {})
        self.assertEqual(p.version, "0.6.9")

    def test_other_packets_ignored(self):
        self.assertIsNone(parser.parse_status("MyGS>OGNFNT,TCPIP*,qAC,GLIDERN2:/101530h4700.00NI01200.00E&/A=001300"))
        self.assertIsNone(parser.parse_status("# javAPRSSrvr 4.1"))
        self.assertIsNone(parser.parse_status(""))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_receives_only_own_station_and_sends_filter(self):
        login_line = []

        async def handle(reader, writer):
            login_line.append((await reader.readline()).decode())
            writer.write(b"# logresp HAOGN unverified, server TEST\r\n")
            writer.write(b"OTHER>OGNFNT,TCPIP*,qAC,TEST:>101530h BDGS:0.1 UP:1min B:9.99V\r\n")
            writer.write(b"mygs>OGNFNT,TCPIP*,qAC,TEST:>101535h BDGS:0.6.9 UP:7min B:4.01V +0.250A P:1.00W\r\n")
            await writer.drain()
            await asyncio.sleep(5)
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]

        got = []
        connection = []
        received = asyncio.Event()

        def on_status(packet):
            got.append(packet)
            received.set()

        c = client.OgnStatusClient("127.0.0.1", port, "MyGS", "HAOGN", on_status, connection.append)
        task = asyncio.create_task(c.run())
        try:
            await asyncio.wait_for(received.wait(), 5)
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            server.close()
            await server.wait_closed()

        self.assertEqual(len(got), 1)  # nur die eigene Station
        self.assertEqual(got[0].values, {"voltage": 4.01, "current": 0.25, "power": 1.0})
        self.assertIn("user HAOGN pass -1", login_line[0])
        self.assertIn("filter b/MyGS", login_line[0])
        self.assertEqual(connection[0], True)
        self.assertEqual(connection[-1], False)  # nach Abbruch gemeldet


if __name__ == "__main__":
    unittest.main()
