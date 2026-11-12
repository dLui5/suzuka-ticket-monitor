import unittest
from unittest.mock import patch

from asoview import ServiceError
from setup_telegram import main, pairing_chat_id


def update(chat_id, chat_type, text):
    return {"message": {"chat": {"id": chat_id, "type": chat_type}, "text": text}}


class GroupSetupTests(unittest.TestCase):
    def test_group_pairing_accepts_groups_and_supergroups(self):
        for kind in ("group", "supergroup"):
            updates = [update(123, "private", "/start@demo_bot unique"),
                       update(-456, kind, "/start@demo_bot unique"),
                       update(-789, kind, "/start@other_bot unique"),
                       update(-111, kind, "/start@demo_bot wrong")]
            self.assertEqual(pairing_chat_id(updates, "demo_bot", "unique", group=True), -456)

    def test_private_pairing_does_not_select_a_group(self):
        updates = [update(-456, "group", "/start unique"), update(123, "private", "/start unique")]
        self.assertEqual(pairing_chat_id(updates, "demo_bot", "unique"), 123)

    def test_missing_or_ambiguous_group_does_not_pick_a_destination(self):
        for updates in ([], [update(-1, "group", "/start@demo_bot unique"),
                             update(-2, "group", "/start@demo_bot unique")]):
            with self.assertRaises(ServiceError):
                pairing_chat_id(updates, "demo_bot", "unique", group=True)

    def test_group_setup_sends_test_to_paired_group_and_prints_id(self):
        with patch("sys.argv", ["setup_telegram.py", "--clipboard", "--group"]), \
                patch("setup_telegram.read_token", return_value="123:abc"), \
                patch("setup_telegram.secrets.token_hex", return_value="unique"), \
                patch("builtins.input", return_value=""), \
                patch("builtins.print") as output, \
                patch("setup_telegram.Telegram") as telegram:
            bot = telegram.return_value
            bot.call.side_effect = [{"username": "demo_bot"},
                                    [update(-456, "group", "/start@demo_bot unique")]]
            main()
            self.assertEqual(bot.chat_id, -456)
            bot.send.assert_called_once()
            output.assert_any_call("TELEGRAM_CHAT_ID: -456")
            self.assertTrue(any("?startgroup=unique" in str(args) for args in output.call_args_list))


if __name__ == "__main__":
    unittest.main()
