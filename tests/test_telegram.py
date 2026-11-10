import io
import subprocess
import unittest
from email.message import Message
from unittest.mock import patch

from asoview import HTTPStatusError, ServiceError, request_json
from telegram import Telegram
from setup_telegram import read_token

TOKEN = "123456789:AAExampleInvalidToken123456789012345"


class Response(io.BytesIO):
    def __init__(self, body, content_type, url):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.status = 200
        self.url = url

    def geturl(self):
        return self.url


class TelegramTests(unittest.TestCase):
    def test_mac_clipboard_bypasses_hidden_terminal_prompt(self):
        with patch("setup_telegram.subprocess.run", return_value=subprocess.CompletedProcess(
            ["pbpaste"], 0, stdout=TOKEN + "\n"
        )) as clipboard, patch("setup_telegram.getpass.getpass") as prompt:
            self.assertEqual(read_token(clipboard=True), TOKEN)
            clipboard.assert_called_once_with(["pbpaste"], capture_output=True, text=True, check=True)
            prompt.assert_not_called()

    def test_clipboard_failure_does_not_expose_contents(self):
        with patch("setup_telegram.subprocess.run", side_effect=subprocess.CalledProcessError(
            1, ["pbpaste"], output=TOKEN, stderr=TOKEN
        )):
            with self.assertRaisesRegex(ServiceError, "Could not read") as caught:
                read_token(clipboard=True)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_invisible_characters_and_terminal_markers_have_safe_diagnostics(self):
        for value, expected in (("\x1b[200~" + TOKEN + "\x1b[201~", "bracketed-paste"),
                                ("\u200b" + TOKEN, "U\\+200B ZERO WIDTH SPACE"),
                                ("", "received no text"),
                                (TOKEN.replace(":", "："), "U\\+FF1A FULLWIDTH COLON")):
            with self.assertRaisesRegex(ServiceError, expected) as caught:
                Telegram(value)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_rejects_malformed_tokens_before_network_request(self):
        with patch("telegram.request_json") as request:
            for token in ("", "bot" + TOKEN, '"' + TOKEN + '"',
                          "https://api.telegram.org/bot" + TOKEN + "/getMe", TOKEN + " extra"):
                with self.subTest(token_type=token[:3]):
                    with self.assertRaisesRegex(ServiceError, "Paste only the token") as caught:
                        Telegram(token)
                    self.assertNotIn(TOKEN, str(caught.exception))
            request.assert_not_called()

    def test_valid_bot_response(self):
        with patch("telegram.request_json", return_value={"ok": True, "result": {"username": "demo_bot"}}):
            self.assertEqual(Telegram(TOKEN).call("getMe"), {"username": "demo_bot"})

    def test_rejected_token_has_actionable_error(self):
        for status in (401, 404):
            with patch("telegram.request_json", side_effect=HTTPStatusError(status)):
                with self.assertRaisesRegex(ServiceError, "token rejected") as caught:
                    Telegram(TOKEN).call("getMe")
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_non_json_response_reports_metadata_without_body_or_url(self):
        url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        for body, content_type, final_url, expected in (
            (f"<html>{TOKEN}</html>".encode(), "text/html", "https://example.com/" + TOKEN, "an HTML page"),
            (b"", "application/json", url, "an empty response"),
            (TOKEN.encode(), "text/plain", url, "invalid JSON"),
        ):
            with patch("urllib.request.urlopen", return_value=Response(body, content_type, final_url)):
                with self.assertRaisesRegex(ServiceError, expected) as caught:
                    Telegram(TOKEN).call("getMe")
                message = str(caught.exception)
                self.assertIn("HTTP 200", message)
                self.assertIn("Telegram getMe", message)
                self.assertNotIn(TOKEN, message)
                self.assertNotIn("example.com", message)
                self.assertEqual("request was redirected" in message, final_url != url)

    def test_json_success_is_still_parsed(self):
        url = "https://example.com/"
        with patch("urllib.request.urlopen", return_value=Response(b'{"ok": true}', "application/json", url)):
            self.assertEqual(request_json(url), {"ok": True})

    def test_incomplete_telegram_response_is_handled(self):
        with patch("telegram.request_json", return_value={"ok": True}):
            with self.assertRaises(ServiceError):
                Telegram(TOKEN).call("getMe")


if __name__ == "__main__":
    unittest.main()
