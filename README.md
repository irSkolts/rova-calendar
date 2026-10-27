# Rova afvalkalender

A subscribable iPhone/Google/Outlook calendar with [Rova](https://www.rova.nl) waste collection days. Rova collects a whole area on the same day, so the calendar applies to every address in that collection area.

**Subscribe:** open <https://irskolts.github.io/rova-calendar/> on your phone and tap *Abonneer in Agenda*, or add this URL as a subscribed calendar:

```
https://irskolts.github.io/rova-calendar/rova.ics
```

Each collection day is an all-day event (GFT and PMD) with a reminder at 19:00 the evening before.

## How it works

- [`rova_calendar.py`](rova_calendar.py) fetches the upcoming collection days from Rova's waste calendar API and writes them to [`docs/rova.ics`](docs/rova.ics). It uses only the Python standard library.
- A [GitHub Actions workflow](.github/workflows/update-calendar.yml) runs it every morning and commits the file only when the schedule changed. The address it looks up is stored as repository secrets, so it is not part of this repository.
- GitHub Pages serves the `docs/` folder, so subscribed calendars pick up new dates (such as next year's schedule) automatically.

## Run it locally

```
python rova_calendar.py --postcode 1234AB --number 1
```

| Option | Meaning |
|---|---|
| `--postcode` | Postcode (required) |
| `--number` | House number (required) |
| `--addition` | House number addition, e.g. `A` |
| `--reminder-hour` | Hour of the reminder on the evening before (default `19`) |
| `--out` | Output file (default `docs/rova.ics`) |

Instead of `--postcode`, `--number` and `--addition` you can set the environment variable `ROVA_ADDRESS`, e.g. `ROVA_ADDRESS="1234AB 1"` or `"1234AB 1 A"`.

## Use it for your own address

1. Fork this repository.
2. Under Settings › Secrets and variables › Actions, add a repository secret `ROVA_ADDRESS` with your postcode and house number, e.g. `1234AB 1`. Keep it as one value: GitHub hides secrets in the public logs, and a separate short secret such as a house number would show up as `***` wherever that digit appears.
3. Under Settings › Pages, publish the `docs/` folder of the `main` branch.
4. Run the *Update calendar* workflow once from the *Actions* tab.

## Notes

- Rova only publishes dates a limited time ahead; the following year usually appears around the turn of the year.
- GitHub disables scheduled workflows after 60 days without repository activity. If the calendar stops updating, re-enable the workflow under the *Actions* tab.
- This is an unofficial project and is not affiliated with Rova.
