"""Pair a new Telegram bot with the person sending a unique /start command."""

import argparse
import getpass
import secrets
import subprocess

from asoview import ServiceError
from telegram import Telegram


def read_token(clipboard=False):
    if clipboard:
        try:
            # Keep credentials in memory; do not pass them as shell arguments or print them.
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            raise ServiceError("Could not read the macOS clipboard. Copy the token and run setup on your Mac.") from None
        return result.stdout.strip()
    return getpass.getpass("Paste the BotFather token (hidden): ").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clipboard", action="store_true", help="Read the token directly from the macOS clipboard")
    args = parser.parse_args()
    print("Paste only the BotFather token, such as 123456789:AA..., without a 'bot' prefix or URL.")
    token = read_token(args.clipboard)
    bot = Telegram(token)
    name = bot.call("getMe")["username"]
    code = secrets.token_hex(8)
    print(f"Open https://t.me/{name}?start={code} and tap Start.")
    input("After tapping Start, press Enter here: ")
    updates = bot.call("getUpdates", {"timeout": 10, "allowed_updates": ["message"]})
    matches = {item["message"]["chat"]["id"] for item in updates
               if item.get("message", {}).get("text") == f"/start {code}"
               and item["message"]["chat"]["type"] == "private"}
    if len(matches) != 1:
        raise ServiceError("Pairing message not found. Run setup again and tap Start on the new link.")
    bot.chat_id = matches.pop()
    bot.send("Telegram is connected to your Circuit Challenger monitor. "
             "Enable the GitHub Actions workflow to start monitoring.")
    print(f"TELEGRAM_CHAT_ID: {bot.chat_id}")
    print("In GitHub repository secrets, save TELEGRAM_BOT_TOKEN (your BotFather token) "
          "and TELEGRAM_CHAT_ID (the number above).")


if __name__ == "__main__":
    try:
        main()
    except (ServiceError, KeyError, EOFError) as error:
        print(f"Setup failed: {error}")
        raise SystemExit(1)
