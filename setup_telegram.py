"""Pair a Telegram bot with a private chat or shared group using a unique /start command."""

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


def pairing_chat_id(updates, name, code, group=False):
    chat_types = {"group", "supergroup"} if group else {"private"}
    command = f"/start@{name} {code}" if group else f"/start {code}"
    matches = set()
    for item in updates:
        message = item.get("message", {})
        chat = message.get("chat", {})
        if message.get("text") == command and chat.get("type") in chat_types:
            matches.add(chat["id"])
    if len(matches) != 1:
        raise ServiceError(
            "Expected a pairing command from exactly one chat. Run setup again, "
            "follow the new link, and send the printed command in your chosen chat."
        )
    return matches.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clipboard", action="store_true", help="Read the token directly from the macOS clipboard")
    parser.add_argument("--group", action="store_true", help="Connect a shared Telegram group instead of a private chat")
    args = parser.parse_args()
    print("Paste only the BotFather token, such as 123456789:AA..., without a 'bot' prefix or URL.")
    token = read_token(args.clipboard)
    bot = Telegram(token)
    name = bot.call("getMe")["username"]
    code = secrets.token_hex(8)
    if args.group:
        print(f"Open https://t.me/{name}?startgroup={code} and select your shared group to add the bot.")
        print(f"In that group, ensure this command has been sent: /start@{name} {code}")
        input("After the command appears in your group, press Enter here: ")
    else:
        print(f"Open https://t.me/{name}?start={code} and tap Start.")
        input("After tapping Start, press Enter here: ")
    updates = bot.call("getUpdates", {"timeout": 10, "allowed_updates": ["message"]})
    bot.chat_id = pairing_chat_id(updates, name, code, args.group)
    bot.send("Telegram is connected to your Circuit Challenger monitor. "
             "Enable the GitHub Actions workflow to start monitoring.")
    print(f"TELEGRAM_CHAT_ID: {bot.chat_id}")
    print("In GitHub repository secrets, save TELEGRAM_BOT_TOKEN (your BotFather token) "
          "and TELEGRAM_CHAT_ID (the number above).")
    if args.group:
        print("Replace the existing TELEGRAM_CHAT_ID secret with this group ID, including its minus sign. "
              "Future notifications will go to the group. This hour's report may already have been sent.")


if __name__ == "__main__":
    try:
        main()
    except (ServiceError, KeyError, EOFError) as error:
        print(f"Setup failed: {error}")
        raise SystemExit(1)
