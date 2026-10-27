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


def fetch(postcode, number, addition):
    url = API.format(postcode=postcode, number=number, addition=addition)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(items, reminder_hour):
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
    for item in sorted(items, key=lambda i: i["date"]):
        day = date.fromisoformat(item["date"][:10])
        waste = item["wasteType"]
        title = TITLES.get(waste["code"], f"Rova: {waste['title']}")
        description = waste.get("notificationTextSameDay") or ""
        if item.get("isIrregular"):
            description += " Let op: afwijkende ophaaldag."
        lines += [
            "BEGIN:VEVENT",
            # Not Rova's own id, which could be traced back to the address.
            f"UID:rova-{day:%Y%m%d}-{waste['code'].lower()}@rovacalendar",
            # Derived from the event so the file only changes when Rova's schedule does.
            f"DTSTAMP:{day:%Y%m%d}T000000Z",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escape(title)}",
            f"DESCRIPTION:{escape(description.strip())}",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{escape(title)} - container vanavond aan de weg zetten",
            f"TRIGGER:{trigger}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # The address can come from the environment so it never has to appear in this repository.
    parser.add_argument("--postcode", default=os.environ.get("ROVA_POSTCODE"))
    parser.add_argument("--number", default=os.environ.get("ROVA_HOUSENUMBER"))
    parser.add_argument("--addition", default=os.environ.get("ROVA_ADDITION", ""))
    parser.add_argument("--reminder-hour", type=int, default=19, help="hour on the evening before (0-23)")
    parser.add_argument("--out", default="docs/rova.ics")
    args = parser.parse_args()
    if not args.postcode or not args.number:
        parser.error("give --postcode and --number, or set ROVA_POSTCODE and ROVA_HOUSENUMBER")

    items = fetch(args.postcode, args.number, args.addition)
    if not items:
        # Keep the previously published calendar rather than replacing it with an empty one.
        raise SystemExit("Rova returned no collection days; not writing calendar")
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(build_ics(items, args.reminder_hour))
    print(f"Wrote {len(items)} collection days to {args.out}")
    for item in sorted(items, key=lambda i: i["date"]):
        print(f"  {item['date'][:10]}  {item['wasteType']['code']}")


if __name__ == "__main__":
    main()
