# Costa Rica hotel availability monitor

This repository is configured to check the 10 hotels hourly using Playwright and Booking.com pages. Hotels 7-10 are checked for both the original date range and the alternative 29 Dec - 31 Dec range. Hotels 1-6 are checked only for their original dates.

## How it works

- Runs manually or every hour at minute 17.
- Opens each Booking page with the requested dates for 2 adults / 1 room.
- Saves the previous availability in `state.json`.
- Sends an email only when a hotel/date combination changes from unavailable to available.
- The email includes the Booking URL and the lowest price shown (EUR).
- Detection uses Booking's room table (`#hprt-table`) vs. the explicit `#no_availability_msg` block. If neither appears (captcha/block/markup change), the check counts as an error; when at least half the checks fail, a one-time warning email is sent so the strategy can be changed.

Scheduled Actions can be delayed during high-load periods; the workflow therefore runs at minute 17 rather than exactly at the top of each hour.

## Setup

1. Create a new GitHub repository and upload all files from this folder.
2. In **Settings -> Secrets and variables -> Actions -> New repository secret**, create:
   - `SMTP_HOST` (e.g. `smtp.gmail.com`)
   - `SMTP_PORT` (`465` for SSL or `587` for STARTTLS)
   - `SMTP_USER` (the email account used to send alerts)
   - `SMTP_PASSWORD` (an app password / SMTP password)
   - `ALERT_TO` (the email address that receives the alert)
3. Make sure the workflow file is on the repository's default branch.
4. Open **Actions -> Hotel availability monitor -> Run workflow** once to test it.
5. Check the Actions log. A healthy run prints `AVAILABLE` or `NO AVAILABILITY` for each hotel/date combination.

## Important caveat

Booking can change page markup or challenge automated traffic. This monitor is not guaranteed to work forever. If a run starts producing errors or implausible results, inspect the Actions log and adjust `ROOM_SELECTOR` / `NO_AVAIL_SELECTOR` in `monitor.py`.

The script never books anything; it only checks the public Booking page and sends an email when availability first appears.
