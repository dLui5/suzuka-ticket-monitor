"""One scheduled availability check. Settings come from environment variables."""

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from asoview import BOOKING_URL, ServiceError, fetch_slots
from telegram import Telegram

JST = timezone(timedelta(hours=9))


def check(state, target, quantity, notifier, now, fetch=fetch_slots):
    """Save alert state only after Telegram accepts the corresponding message."""
    key = f"{target}/{quantity}"
    if state.get("watch") != key:
        state.clear()
        state["watch"] = key
    if now.date() > date.fromisoformat(target):
        if not state.get("finished"):
            notifier.send(f"Monitoring finished: {target} has passed in Japan. Disable the GitHub workflow.")
            state["finished"] = True
        return

    try:
        slots = fetch(target, quantity)
    except ServiceError:
        state["failures"] = state.get("failures", 0) + 1
        if state["failures"] >= 3 and not state.get("failure_alerted"):
            notifier.send("Ticket monitor: 3 or more checks failed. Availability is unknown. "
                          "Please check GitHub Actions logs; checking will continue.")
            state["failure_alerted"] = True
        raise

    # A Telegram failure must not be counted as a successful check or clear an alert.
    if state.get("failure_alerted"):
        notifier.send("Ticket monitor: availability checks have recovered.")
        state["failure_alerted"] = False
    state["failures"] = 0
    previous = set(state.get("available", []))
    current = [f"{s.id}/{s.start}/{s.end}" for s in slots]
    new_slots = [s for s, key in zip(slots, current) if key not in previous]
    if new_slots:
        times = "\n".join(f"• {s.start}–{s.end} JST: {s.remaining} remaining" for s in new_slots)
        notifier.send(f"🎟 Circuit Challenger tickets available!\n{target} · {quantity} tickets in the same slot\n"
                      f"{times}\n\nBook now: {BOOKING_URL}\nAvailability can change before checkout.")
    state["available"] = current
    hour = now.strftime("%Y-%m-%dT%H")
    if state.get("heartbeat") != hour:
        status = "Tickets are available!!!" if slots else "No tickets."
        notifier.send(f"{status}\n"
                      f"{now:%Y-%m-%d %H:%M} JST.\n"
                      )
        state["heartbeat"] = hour


def load_state(path):
    if not path.exists():
        return {}
    state = json.loads(path.read_text())
    if not isinstance(state, dict):
        raise ValueError("State must be a JSON object")
    return state


def save_state(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Check live stock without Telegram or saved state")
    args = parser.parse_args()
    target = os.environ.get("TARGET_DATE", "2026-11-25")
    date.fromisoformat(target)
    quantity = int(os.environ.get("TICKET_QUANTITY", "2"))
    if quantity < 1:
        raise ValueError("TICKET_QUANTITY must be positive")
    if args.dry_run:
        slots = fetch_slots(target, quantity)
        print(json.dumps({"date": target, "quantity": quantity,
                          "slots": [vars(slot) for slot in slots]}, ensure_ascii=False))
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first")
    path = Path("state.json")
    state = load_state(path)
    try:
        check(state, target, quantity, Telegram(token, chat_id), datetime.now(JST))
    finally:
        save_state(path, state)
    print(f"Checked {target} for {quantity} tickets. Matching slots: {len(state.get('available', []))}")


if __name__ == "__main__":
    try:
        main()
    except (ServiceError, ValueError, OSError) as error:
        print(f"Monitor failed: {error}", flush=True)
        raise SystemExit(1)
