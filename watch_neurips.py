#!/usr/bin/env python3
"""
Watch the public NeurIPS 2026 registration page and send a push notification
as soon as a Sydney session is no longer marked "Sold Out".

The page https://neurips.cc/Register/view-registration is public (no login
needed) and lists each session as e.g.
    (Sold Out):  Sydney Conference & Tutorials  This session is sold out.
When a spot frees up, the "(Sold Out)" markers disappear for that session.

Usage
  python watch_neurips.py            # loop forever, check every INTERVAL seconds
  python watch_neurips.py --once     # single check (for cron / GitHub Actions)

Config (environment variables)
  NTFY_TOPIC     ntfy.sh topic to push to (pick something long and random)
  SESSIONS       comma-separated session names to watch
                 default: "Sydney Conference & Tutorials,Sydney Workshops & Competitions"
  INTERVAL       seconds between checks in loop mode (default 120)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO   optional email alert
"""
import os, sys, time, smtplib, argparse, datetime
from email.message import EmailMessage

import requests
from bs4 import BeautifulSoup

URL = "https://neurips.cc/Register/view-registration"
HEADERS = {"User-Agent": "neurips-sydney-availability-watcher (personal, low-frequency)"}

SESSIONS = [s.strip() for s in os.environ.get(
    "SESSIONS", "Sydney Conference & Tutorials,Sydney Workshops & Competitions"
).split(",") if s.strip()]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
INTERVAL = int(os.environ.get("INTERVAL", "120"))
REMIND_EVERY = 600  # loop mode: re-notify every 10 min while still available


def log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def check():
    """Return {session: 'available' | 'sold_out' | 'missing'}."""
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]

    status = {}
    for name in SESSIONS:
        idxs = [i for i, l in enumerate(lines) if l == name]
        if not idxs:
            # fall back to substring match in case of extra punctuation
            idxs = [i for i, l in enumerate(lines) if name.lower() in l.lower()]
        if not idxs:
            status[name] = "missing"
            continue
        i = idxs[-1]  # the one in the "Choose Sessions" list
        prev = lines[i - 1].lower() if i > 0 else ""
        nxt = lines[i + 1].lower() if i + 1 < len(lines) else ""
        # "(Sold Out):" marker sits right before the name, "This session is
        # sold out." right after it. (The previous session's trailing
        # sentence must not count, so only the "(sold out)" form is accepted
        # on the preceding line.)
        sold = "(sold out)" in prev or nxt.startswith("this session is sold out")
        status[name] = "sold_out" if sold else "available"
    return status


def notify(title, body, urgent=True):
    log(f"NOTIFY: {title} | {body}")
    if NTFY_TOPIC:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=body.encode(),
                headers={
                    "Title": title,
                    "Priority": "urgent" if urgent else "default",
                    "Tags": "ticket,rotating_light" if urgent else "warning",
                    "Click": URL,
                },
                timeout=15,
            )
        except Exception as e:
            log(f"ntfy failed: {e}")
    if os.environ.get("SMTP_HOST") and os.environ.get("EMAIL_TO"):
        try:
            msg = EmailMessage()
            msg["Subject"] = title
            msg["From"] = os.environ.get("SMTP_USER", "")
            msg["To"] = os.environ["EMAIL_TO"]
            msg.set_content(f"{body}\n\n{URL}")
            with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
                s.starttls()
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
                s.send_message(msg)
        except Exception as e:
            log(f"email failed: {e}")


def run_once():
    status = check()
    log(status)
    avail = [s for s, v in status.items() if v == "available"]
    missing = [s for s, v in status.items() if v == "missing"]
    if avail:
        notify("NeurIPS Sydney tickets AVAILABLE",
               "Open now: " + ", ".join(avail) + ". Register fast!")
    elif missing:
        notify("NeurIPS watcher: page changed",
               "Couldn't find: " + ", ".join(missing) + ". Check the page manually.",
               urgent=False)
    return status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single check, then exit")
    ap.add_argument("--test-notify", action="store_true", help="send a test notification")
    args = ap.parse_args()

    if args.test_notify:
        notify("NeurIPS watcher test", "If you see this, notifications work.", urgent=False)
        return
    if args.once:
        run_once()
        return

    log(f"Watching {SESSIONS} every {INTERVAL}s")
    last_alert = 0.0
    while True:
        try:
            status = check()
            log(status)
            avail = [s for s, v in status.items() if v == "available"]
            missing = [s for s, v in status.items() if v == "missing"]
            if (avail or missing) and time.time() - last_alert > REMIND_EVERY:
                if avail:
                    notify("NeurIPS Sydney tickets AVAILABLE",
                           "Open now: " + ", ".join(avail) + ". Register fast!")
                else:
                    notify("NeurIPS watcher: page changed",
                           "Couldn't find: " + ", ".join(missing) + ". Check manually.",
                           urgent=False)
                last_alert = time.time()
            elif not avail and not missing:
                last_alert = 0.0  # reset so the next opening alerts immediately
        except Exception as e:
            log(f"check failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
