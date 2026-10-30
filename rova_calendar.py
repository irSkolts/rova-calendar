"""Generate an iCalendar (.ics) file with Rova waste collection days for one address."""

import argparse
import json
import os
import urllib.request
from datetime import date, timedelta

API = "https://www.rova.nl/api/waste-calendar/upcoming?postalcode={postcode}&houseNumber={number}&addition={addition}&take=500"

TITLES = {
    "GFT": "Rova: GFT (groente, fruit, tuin) 🟢",
    "PMD": "Rova: PMD (plastic, blik, drinkpakken) 🟠",
    "RESTAFVAL": "Rova: Restafval ⚫",
    "PAPIER": "Rova: Papier 🔵",
}
PAPER_TITLE = "Oud papier 🔵"


def fetch(postcode, number, addition):
    url = API.format(postcode=postcode, number=number, addition=addition)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def rova_events(items):
    for item in items:
        waste = item["wasteType"]
        title = TITLES.get(waste["code"], f"Rova: {waste['title']}")
        description = waste.get("notificationTextSameDay") or ""
        if item.get("isIrregular"):
            description += " Let op: afwijkende ophaaldag."
        yield {
            "day": date.fromisoformat(item["date"][:10]),
            "code": waste["code"].lower(),
            "title": title,
            "description": description.strip(),
            "alarm": f"{title} - container vanavond aan de weg zetten",
        }


def last_saturday(year, month):
    first_of_next = date(year + month // 12, month % 12 + 1, 1)
    last = first_of_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - 5) % 7)


def paper_days(changes_file, today, months=12):
    """Last Saturday of each month from today on, with the moves and cancellations in changes_file.

    Each line of changes_file is "YYYY-MM-DD = YYYY-MM-DD" (moved) or "YYYY-MM-DD = -" (cancelled);
    text after # is ignored.
    """
    changes = {}
    with open(changes_file, encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                regular, _, actual = (part.strip() for part in line.partition("="))
                changes[date.fromisoformat(regular)] = None if actual == "-" else date.fromisoformat(actual)
    days = []
    for i in range(months + 1):
        year, month = today.year + (today.month - 1 + i) // 12, (today.month - 1 + i) % 12 + 1
        day = changes.get(last_saturday(year, month), last_saturday(year, month))
        if day and day >= today:
            days.append(day)
    return days


def paper_events(days):
    for day in days:
        yield {
            "day": day,
            "code": "oudpapier",
            "title": PAPER_TITLE,
            "description": "Oud papier vóór 8.00 uur aan de weg zetten, in een doos of stevig dichtgebonden.",
            "alarm": f"{PAPER_TITLE} - morgen vóór 8.00 uur aan de weg zetten",
        }


def build_ics(events, reminder_hour):
    # All-day events start at midnight, so a negative offset lands on the evening before.
    trigger = f"-PT{24 - reminder_hour}H"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RovaCalendar//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Rova afvalkalender",
        "X-WR-TIMEZONE:Europe/Amsterdam",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:P1D",
    ]
    for event in sorted(events, key=lambda e: (e["day"], e["code"])):
        day = event["day"]
        lines += [
            "BEGIN:VEVENT",
            # Not Rova's own id, which could be traced back to the address.
            f"UID:rova-{day:%Y%m%d}-{event['code']}@rovacalendar",
            # Derived from the event so the file only changes when Rova's schedule does.
            f"DTSTAMP:{day:%Y%m%d}T000000Z",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escape(event['title'])}",
            f"DESCRIPTION:{escape(event['description'])}",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{escape(event['alarm'])}",
            f"TRIGGER:{trigger}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # The address can come from ROVA_ADDRESS ("1234AB 5" or "1234AB 5 A") so it never has to
    # appear in this repository. One combined value also keeps GitHub's secret masking from
    # revealing a short house number by blanking out every matching digit in the logs.
    env = (os.environ.get("ROVA_ADDRESS") or "").split()
    parser.add_argument("--postcode", default=env[0] if len(env) > 0 else None)
    parser.add_argument("--number", default=env[1] if len(env) > 1 else None)
    parser.add_argument("--addition", default=env[2] if len(env) > 2 else "")
    parser.add_argument("--reminder-hour", type=int, default=19, help="hour on the evening before (0-23)")
    parser.add_argument("--paper", metavar="FILE", help="also add paper collections on the last Saturday "
                        "of each month, with the changes listed in FILE (see oud_papier.txt)")
    parser.add_argument("--out", default="docs/rova.ics")
    args = parser.parse_args()
    if not args.postcode or not args.number:
        parser.error("give --postcode and --number, or set ROVA_ADDRESS")

    items = fetch(args.postcode, args.number, args.addition)
    if not items:
        # Keep the previously published calendar rather than replacing it with an empty one.
        raise SystemExit("Rova returned no collection days; not writing calendar")
    events = list(rova_events(items))
    if args.paper:
        events += paper_events(paper_days(args.paper, date.today()))
    events.sort(key=lambda e: (e["day"], e["code"]))
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(build_ics(events, args.reminder_hour))
    print(f"Wrote {len(events)} collection days to {args.out}")
    for event in events:
        print(f"  {event['day']}  {event['code']}")


if __name__ == "__main__":
    main()
