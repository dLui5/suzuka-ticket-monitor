import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from asoview import ServiceError, Slot, available_slots, request_json
from monitor import JST, check, load_state, save_state


class Notifier:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send(self, message):
        if self.fail:
            raise ServiceError("Telegram unavailable")
        self.messages.append(message)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.notifier = Notifier()
        self.now = datetime(2026, 11, 10, 12, tzinfo=JST)
        self.slots = [Slot("02", "12:20", "12:30", 12)]

    def run_check(self, slots=None, fetch=None):
        check(self.state, "2026-11-25", 2, self.notifier, self.now,
              fetch or (lambda *_: self.slots if slots is None else slots))

    def test_live_fixtures(self):
        root = Path(__file__).parent / "fixtures"
        self.assertEqual(available_slots(json.loads((root / "nov25.json").read_text()), 2), [])
        courses = json.loads((root / "nov26.json").read_text())
        self.assertEqual(available_slots(courses, 2), self.slots)
        self.assertEqual(available_slots(courses, 13), [])
        # Two places spread across different slots cannot satisfy the request.
        one = copy.deepcopy(courses[1])
        one["remainReserveNumber"] = 1
        self.assertEqual(available_slots([one, {**one, "id": "other"}], 2), [])
        for field, value in (("isClosed", True), ("isRequest", True),
                             ("stockStatus", "STOCK_OUT"),
                             ("maximumReservableQuantity", 1),
                             ("minimumReservableQuantity", 3)):
            with self.subTest(field=field):
                self.assertEqual(available_slots([{**courses[1], field: value}], 2), [])

    def test_errors_and_schema_changes_are_not_sold_out(self):
        for bad in ({"code": "INTERNAL_SERVER_ERROR"}, [{}], [None]):
            with self.assertRaises(ServiceError):
                available_slots(bad, 2)

    def test_dedup_restock_and_quantity_fluctuations(self):
        self.run_check()
        self.assertEqual(len(self.notifier.messages), 2)  # Alert and daily confirmation.
        self.slots = [Slot("02", "12:20", "12:30", 11)]
        self.run_check()
        self.assertEqual(len(self.notifier.messages), 2)
        self.run_check(slots=[])
        self.run_check()
        self.assertEqual(len(self.notifier.messages), 3)

    def test_failed_delivery_is_retried(self):
        self.notifier.fail = True
        with self.assertRaises(ServiceError):
            self.run_check()
        self.assertNotIn("available", self.state)
        self.notifier.fail = False
        self.run_check()
        self.assertIn("tickets available", self.notifier.messages[0])

    def test_check_failure_preserves_stock_and_alerts_once_then_recovers(self):
        self.run_check()
        previous = self.state["available"][:]

        def broken(*_):
            raise ServiceError("HTTP 503")

        for _ in range(4):
            with self.assertRaises(ServiceError):
                self.run_check(fetch=broken)
        self.assertEqual(self.state["available"], previous)
        self.assertEqual(sum("checks failed" in x for x in self.notifier.messages), 1)
        self.run_check()
        self.assertEqual(sum("recovered" in x for x in self.notifier.messages), 1)
        self.assertEqual(sum("tickets available" in x for x in self.notifier.messages), 1)

    def test_daily_heartbeat_and_expiration(self):
        self.run_check(slots=[])
        self.now = datetime(2026, 11, 11, 0, tzinfo=JST)
        self.run_check(slots=[])
        self.assertEqual(len(self.notifier.messages), 2)
        self.now = datetime(2026, 11, 26, 0, tzinfo=JST)
        self.run_check(fetch=lambda *_: self.fail("Expired date must not be polled"))
        self.run_check(fetch=lambda *_: self.fail("Expired date must not be polled"))
        self.assertEqual(len(self.notifier.messages), 3)

    def test_state_survives_restart(self):
        self.run_check()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            save_state(path, self.state)
            self.state = load_state(path)
        self.run_check()
        self.assertEqual(len(self.notifier.messages), 2)

    def test_transport_error_does_not_expose_token(self):
        import urllib.error
        secret_url = "https://api.telegram.org/botSECRET/sendMessage"
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            secret_url, 401, "Unauthorized", None, None
        )):
            with self.assertRaisesRegex(ServiceError, "^HTTP 401$"):
                request_json(secret_url)


if __name__ == "__main__":
    unittest.main()
