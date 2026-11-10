"""Telegram API calls, with credentials excluded from errors."""

import re
import unicodedata

from asoview import HTTPStatusError, ServiceError, request_json


class Telegram:
    def __init__(self, token, chat_id=None):
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            if not token:
                reason = "The prompt received no text."
            elif "\x1b[200~" in token or "\x1b[201~" in token:
                reason = "The terminal included bracketed-paste control markers."
            elif token.startswith("bot") or "://" in token:
                reason = "The input includes a 'bot' prefix or URL."
            else:
                unexpected = [char for char in token if not re.fullmatch(r"[0-9A-Za-z_:-]", char)]
                if unexpected:
                    # Only identify characters outside the token alphabet, never token text.
                    names = sorted({f"U+{ord(char):04X} {unicodedata.name(char, 'CONTROL CHARACTER')}"
                                    for char in unexpected})
                    reason = "Unexpected characters: " + ", ".join(names) + "."
                elif token.count(":") != 1:
                    reason = "The input must contain exactly one ordinary colon (:)."
                else:
                    reason = "The part before the colon must be digits and the part after it must not be empty."
            raise ServiceError(
                f"Invalid bot token format. {reason} Paste only the token from BotFather. "
                "On macOS, try python3 setup_telegram.py --clipboard to bypass terminal pasting."
            )
        self.token = token
        self.chat_id = chat_id

    def call(self, method, payload=None):
        try:
            result = request_json(f"https://api.telegram.org/bot{self.token}/{method}", payload or {})
        except HTTPStatusError as error:
            if error.status in (401, 404):
                raise ServiceError(
                    f"Telegram {method}: token rejected (HTTP {error.status}). "
                    "Copy the current token from BotFather and try again."
                ) from None
            raise ServiceError(f"Telegram {method}: {error}") from None
        except ServiceError as error:
            raise ServiceError(
                f"Telegram {method}: {error}. If the token is copied correctly, "
                "check whether a VPN, proxy, or network filter is intercepting api.telegram.org."
            ) from None
        if not isinstance(result, dict) or result.get("ok") is not True or "result" not in result:
            raise ServiceError("Telegram rejected the request; check the token and chat ID")
        return result["result"]

    def send(self, text):
        self.call("sendMessage", {"chat_id": self.chat_id, "text": text,
                                  "link_preview_options": {"is_disabled": True}})
