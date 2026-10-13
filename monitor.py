import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "state.json"

ALERTS = [
    {
        "name": "Hotel Lomas del Volcan",
        "url": "https://www.booking.com/hotel/cr/lomas-del-volcan.es.html",
        "checkin": "2026-12-25", "checkout": "2026-12-27",
    },
    {
        "name": "Tifakara by the Waterfall",
        "url": "https://www.booking.com/hotel/cr/tifakara-lodge.es.html",
        "checkin": "2026-12-25", "checkout": "2026-12-27",
    },
    {
        "name": "La Fortuna Retreat",
        "url": "https://www.booking.com/hotel/cr/fortuna-retreat.es.html",
        "checkin": "2026-12-25", "checkout": "2026-12-27",
    },
    {
        "name": "Hotel Boutique Casa del Rio",
        "url": "https://www.booking.com/hotel/cr/casa-del-rio-la-fortuna.es.html",
        "checkin": "2026-12-25", "checkout": "2026-12-27",
    },
    {
        "name": "El Establo Mountain",
        "url": "https://www.booking.com/hotel/cr/el-establo-mountain.es.html",
        "checkin": "2026-12-27", "checkout": "2026-12-28",
    },
    {
        "name": "Ecotica Boutique",
        "url": "https://www.booking.com/hotel/cr/byblos.es.html",
        "checkin": "2026-12-27", "checkout": "2026-12-28",
    },
    {
        "name": "River Lodge",
        "url": "https://www.booking.com/hotel/cr/river-lodge.es.html",
        "checkin": "2026-12-28", "checkout": "2026-12-31",
        "alternate": {"checkin": "2026-12-29", "checkout": "2026-12-31"},
    },
    {
        "name": "Tiki Villas Rainforest Lodge",
        "url": "https://www.booking.com/hotel/cr/tikivillas-rainforest-lodge.es.html",
        "checkin": "2026-12-28", "checkout": "2026-12-31",
        "alternate": {"checkin": "2026-12-29", "checkout": "2026-12-31"},
    },
    {
        "name": "Rancho Pacifico",
        "url": "https://www.booking.com/hotel/cr/rancho-pacifico.es.html",
        "checkin": "2026-12-28", "checkout": "2026-12-31",
        "alternate": {"checkin": "2026-12-29", "checkout": "2026-12-31"},
    },
    {
        "name": "Nature's Edge",
        "url": "https://www.booking.com/hotel/cr/nature-39-s-edge-cabinas.es.html",
        "checkin": "2026-12-28", "checkout": "2026-12-31",
        "alternate": {"checkin": "2026-12-29", "checkout": "2026-12-31"},
    },
]

# DOM signals verified against Booking hotel pages (Oct 2026):
# - available: room table with quantity selectors
# - unavailable: explicit "No tenemos disponibilidad..." block
ROOM_SELECTOR = "#hprt-table select.hprt-nos-select"
PRICE_SELECTOR = "#hprt-table .hprt-price-block .bui-price-display__value"
NO_AVAIL_SELECTOR = "#no_availability_msg"

AVAILABLE, UNAVAILABLE, UNKNOWN = "available", "unavailable", "unknown"


class BlockedError(Exception):
    pass


def booking_url(base_url: str, checkin: str, checkout: str) -> str:
    p = urlparse(base_url)
    q = dict(parse_qsl(p.query))
    q.update({
        "checkin": checkin, "checkout": checkout,
        "group_adults": "2", "no_rooms": "1", "group_children": "0",
        "selected_currency": "EUR",
    })
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q), p.fragment))


def parse_price(text: str):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def inspect_page(page, alert, checkin, checkout):
    url = booking_url(alert["url"], checkin, checkout)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector(f"{ROOM_SELECTOR}, {NO_AVAIL_SELECTOR}", state="attached", timeout=25000)
    except PlaywrightTimeoutError:
        pass

    rooms = page.locator(ROOM_SELECTOR).count()
    no_avail = page.locator(NO_AVAIL_SELECTOR)
    no_avail_visible = no_avail.count() > 0 and no_avail.first.is_visible()

    if rooms > 0:
        status = AVAILABLE
    elif no_avail_visible:
        status = UNAVAILABLE
    else:
        status = UNKNOWN

    price = None
    if status == AVAILABLE:
        prices = [parse_price(t) for t in page.locator(PRICE_SELECTOR).all_inner_texts()]
        prices = [x for x in prices if x]
        price = f"{min(prices)} EUR" if prices else None

    if status == UNKNOWN:
        raise BlockedError(f"no availability signals found (title: {page.title()!r}, url: {page.url[:150]})")

    return {
        "available": status == AVAILABLE,
        "price": price,
        "rooms": rooms,
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def notify(subject, body):
    """Open a GitHub issue that @mentions the owner, so GitHub sends an email/mobile notification."""
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        print(f"GitHub not configured, skipping notification:\n{subject}\n{body}")
        return
    mention = os.getenv("NOTIFY_USER") or repo.split("/")[0]
    payload = json.dumps({"title": subject, "body": f"@{mention}\n\n{body}"}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Notification issue created:", json.loads(resp.read())["html_url"])


def main():
    if os.getenv("TEST_NOTIFICATION") == "true":
        notify("✅ Prueba de aviso - monitor de hoteles", "Si recibes esto, las alertas funcionan. Puedes cerrar este issue.")
    state = load_state()
    meta = state.setdefault("_meta", {})
    found, errors = [], []
    checks = 0
    headless = os.getenv("HEADLESS", "1") != "0"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        for alert in ALERTS:
            dates = [(alert["checkin"], alert["checkout"])]
            if alert.get("alternate"):
                dates.append((alert["alternate"]["checkin"], alert["alternate"]["checkout"]))
            for checkin, checkout in dates:
                key = f"{alert['name']}|{checkin}|{checkout}"
                checks += 1
                try:
                    result = inspect_page(page, alert, checkin, checkout)
                    prior = state.get(key, {})
                    state[key] = result
                    # Alert only on transition to available (also on first run if already available).
                    if result["available"] and not prior.get("available", False):
                        found.append({"name": alert["name"], "checkin": checkin, "checkout": checkout, **result})
                    print(key, "AVAILABLE" if result["available"] else "NO AVAILABILITY", result["price"] or "")
                except Exception as exc:
                    errors.append(f"{key}: {type(exc).__name__}: {exc}")
                    print("ERROR", key, exc, file=sys.stderr)
                time.sleep(2)
        context.close()
        browser.close()

    if found:
        lines = ["¡Disponibilidad detectada en Booking!\n"]
        for x in found:
            lines.append(f"- **{x['name']}** | {x['checkin']} -> {x['checkout']} | Desde: {x['price'] or 'ver Booking'}\n  {x['url']}\n")
        notify("🏨 Disponibilidad de hotel encontrada - Costa Rica", "\n".join(lines))
        print(f"Sent {len(found)} availability alert(s).")

    # Warn (once per incident) when Booking appears to block most checks, so the strategy can be changed.
    blocked = checks > 0 and len(errors) >= max(1, checks // 2)
    if blocked and not meta.get("blocked_alert_sent"):
        notify(
            "⚠️ Monitor de hoteles: Booking parece estar bloqueando",
            f"{len(errors)}/{checks} comprobaciones fallaron. Puede ser captcha/bloqueo de Booking "
            "o un cambio en la web. Hay que cambiar de estrategia.\n\n" + "\n".join(errors),
        )
        meta["blocked_alert_sent"] = True
    elif not blocked:
        meta["blocked_alert_sent"] = False
    meta["last_run"] = datetime.now(timezone.utc).isoformat()
    meta["last_errors"] = len(errors)

    save_state(state)
    if errors:
        # Fail the run so GitHub Actions makes the diagnostic visible.
        print("\nErrors:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
