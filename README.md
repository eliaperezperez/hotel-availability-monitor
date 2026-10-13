# Costa Rica hotel availability monitor

This repository is configured to check the 10 hotels hourly using Playwright and Booking.com pages. Hotels 7-10 are checked for both the original date range and the alternative 29 Dec - 31 Dec range. Hotels 1-6 are checked only for their original dates.

## How it works

- Runs manually or every hour at minute 23.
- Opens each Booking page with the requested dates for 2 adults / 1 room.
- Saves the previous availability in `state.json`.
- Opens a notification issue only when a hotel/date combination changes from unavailable to available.
- The issue includes the Booking URL and the lowest price shown (EUR).
- Detection uses Booking's room table (`#hprt-table`) vs. the explicit `#no_availability_msg` block. If neither appears (captcha/block/markup change), the check counts as an error; when at least half the checks fail, a one-time warning issue is opened so the strategy can be changed.

Scheduled Actions can be delayed during high-load periods; the workflow therefore runs at minute 23 rather than exactly at the top of each hour.

## Setup

No secrets needed. Alerts are delivered as GitHub issues that @mention the repo owner, so GitHub sends an email / mobile notification (check https://github.com/settings/notifications -> Participating, @mentions -> Email is enabled).

1. Make sure the workflow file is on the repository's default branch.
2. Open **Actions -> Hotel availability monitor -> Run workflow**, tick **Send a test notification issue**, and run it to verify you receive the alert.
3. A healthy run prints `AVAILABLE` or `NO AVAILABILITY` for each hotel/date combination.

## Important caveat

Booking can change page markup or challenge automated traffic. This monitor is not guaranteed to work forever. If a run starts producing errors or implausible results, inspect the Actions log and adjust `ROOM_SELECTOR` / `NO_AVAIL_SELECTOR` in `monitor.py`.

The script never books anything; it only checks the public Booking page and notifies you when availability first appears.
