# Circuit Challenger ticket monitor

Watches **25 November 2026 for any available tickets (at least one ticket in any time slot)**, at any time of day (Japan time), and sends Telegram notifications. The ticket is Suzuka Circuit's [Circuit Challenger, East Course](https://www.asoview.com/item/ticket/ticket0000007351/), plan `ticket0000007351`.

**One ticket is one kart**, per the product's `1台` purchase category. Check the attraction's occupancy rules if you plan to share a kart.

## Free hosting: GitHub Actions

This workflow requests a check every five minutes, around the clock. [Standard GitHub-hosted runners are free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). Choose a **public repository** for the free setup; private repositories have usage limits. The repository contains code and non-secret alert history; the Telegram token and chat ID go in GitHub Actions secrets.

[GitHub scheduled workflows can be delayed or dropped](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). This is best-effort monitoring, with no guaranteed detection time. The first run should be triggered manually. Schedules only run from the default branch, and public-repository schedules are disabled after 60 days without repository activity. Enable GitHub's Actions failure emails as an additional signal: a stopped workflow cannot send its own Telegram warning.

## 1. Create your Telegram bot

1. Open the official [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow the prompts to choose a name and a username ending in `bot`.
3. Keep the token BotFather gives you private. Do not paste it into chat or commit it.
4. In this project directory, run `python3 setup_telegram.py` (Python 3.10 or newer; no packages to install).
5. Paste the token at the hidden prompt. Open the unique Telegram link printed by the script, tap **Start**, then return to the terminal and press Enter.
6. You should receive a Telegram test message. The terminal prints your `TELEGRAM_CHAT_ID`; save it for the next step.

The pairing script saves no credentials. It requires a new bot with no webhook or competing consumer of `getUpdates`. See [Telegram's official setup guide](https://core.telegram.org/bots/tutorial).

If setup fails, paste only the token itself (`digits:letters`), without a `bot` prefix, quotes, or a URL. A rejected token produces HTTP 401/404. An HTML, empty, or invalid-JSON response is different: setup now reports the HTTP status and whether the request was redirected, without printing the token or response body. If it persists with a correctly copied token, check your VPN, proxy, or network filter, or try another network. Share only the printed error message for troubleshooting.

If you copied the exact token but the hidden prompt rejects it, copy the token again and run `python3 setup_telegram.py --clipboard` on your Mac. This reads directly from the clipboard, bypassing terminal paste handling, and never prints or saves the token. Format errors now identify empty input, terminal paste markers, or unexpected Unicode characters without displaying the token itself.

## Send alerts to a shared Telegram group

1. Create a Telegram group with everyone who should receive alerts.
2. Copy your existing BotFather token, then run `python3 setup_telegram.py --clipboard --group` on your Mac.
3. Open the printed link and select the group to add the bot. Ensure the exact `/start@YourBot ...` command printed by setup appears in the group; send it yourself if necessary. This uses Telegram's [group deep linking](https://core.telegram.org/bots/features#deep-linking).
4. Return to the terminal and press Enter. Setup sends a test message to the group and prints its `TELEGRAM_CHAT_ID`.
5. In your GitHub repository, open **Settings → Secrets and variables → Actions**, edit **TELEGRAM_CHAT_ID**, and replace its value with the group ID, including the leading minus sign. Keep your existing **TELEGRAM_BOT_TOKEN**.

Subsequent monitor runs use the group as their notification destination. You and your friend receive alerts in that group rather than separate private chats. The test message confirms group delivery; normal runs still suppress duplicate alerts and this hour's report may already have been sent. A code push is not needed to change the destination secret. The bot must remain in the group and be allowed to send messages.

## 2. Put this project on GitHub

1. Create a new **public** GitHub repository, for example `suzuka-ticket-monitor`.
2. Upload the project files, including `.github/workflows/monitor.yml`, to its default branch. Using Git to push this directory preserves hidden files. Never upload credentials or `state.json`.
3. Open **Settings → Secrets and variables → Actions → New repository secret**. Add:
   - `TELEGRAM_BOT_TOKEN`: the token from BotFather.
   - `TELEGRAM_CHAT_ID`: the number printed by the pairing script.
4. Ensure repository rules permit the workflow to write to the `monitor-state` branch. The workflow requests `contents: write`; organization policies can override it.
5. Open **Actions → Ticket monitor → Run workflow**. Check that all steps pass and that you receive the first monitoring confirmation in Telegram.
6. Scheduled runs will then continue while your Mac is off. Check Actions run history to verify that scheduled checks are actually executing.

No website, credit card, database service, or Asoview login is needed for this implementation. No deployment or GitHub repository has been created automatically.

## Notifications

- Alert when a slot first has at least one ticket; include the time, reported stock, and booking link.
- Suppress repeat alerts while the same slot remains available, including stock count fluctuations.
- Alert again if a slot becomes unavailable and later reopens.
- Send a status report on the first successful check of each clock hour in Japan. Reports include whether matching tickets are available; delivery follows the next successful run, rather than occurring at an exact minute. Failed report deliveries are retried on subsequent checks.
- Warn after three consecutive failed availability checks, then send a recovery message when checks succeed again. Failed requests and unexpected data are never treated as sold-out results.
- Retry failed Telegram deliveries on a later run. A crash after Telegram accepts an alert but before history is saved can cause a duplicate; delivery and Git persistence cannot be one atomic operation.
- Stop polling Asoview after 25 November ends in Japan and send one completion message. **Disable the workflow** from its Actions menu afterward to stop scheduled GitHub runs.

History lives on a separate `monitor-state` branch containing only `state.json`, and is updated only when alert state changes. Overlapping scheduled/manual runs are serialized. Restoring history must succeed before checking tickets, preventing repeated alerts if Git state becomes unavailable. If saving history fails, the Actions run fails and the next run can repeat an alert.

This monitor reads the public `/stocks/ticket/courses` endpoint used by the ticket page. It accepts open `REALTIME` slots with sufficient `remainReserveNumber` and applicable minimum/maximum quantity limits. No checkout, reservation, or purchase is performed. Stock can change before you complete a purchase. The endpoint is not a documented third-party API; site changes can require updating the parser.

## Local checks

Read live stock without Telegram or modifying alert history:

```sh
python3 monitor.py --dry-run
TARGET_DATE=2026-11-26 python3 monitor.py --dry-run
```

Change `TARGET_DATE` and `TICKET_QUANTITY` in `.github/workflows/monitor.yml` to change the watch. All slot times and expiry dates use Japan time.

Run the tests:

```sh
python3 -m unittest discover -s tests -v
```

The fixtures were captured from the public stock endpoint on 10 November 2026: 25 November returned no slots, and 26 November returned one open 12:20–12:30 slot with 12 remaining. These are snapshots, not a guarantee of current stock.
