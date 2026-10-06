# holiday-planner

Mark's holiday planner. Its goal is to help him pick the best days to take
off in a planning year. To do that it overlays the children's school calendar and
Alba's university calendar, so he can see at a glance when everyone is free.

A day split yellow and blue is a working day when *everyone* is free, the only kind
that counts when booking a proper block. Red is a national or regional public
holiday, purple a Sabadell local one, yellow a school-only day, blue a
university-only day.

The page has three tabs:

- **Days off** - every break in the year (booked days plus public holidays and the
  weekends around them), grouped by month, with what each one costs. Filter by
  upcoming or taken, and by breaks that use your days or holidays only.
- **Plan** - the calendar, filterable by month, with the **Best days** list. That
  ranks every open day the family is free by the unbroken break it would give, and
  re-ranks as you book. Filter it by who must be free, minimum break length and
  music-class days.
- **Allowance** - the year's numbers, Compensation Days and the rules.

A booked day counts as **taken** once its date has passed. Release a past day you
worked after all and it returns to the allowance. Bookings are saved to the days-off
file (see below); only view settings such as the open tab stay in the browser.

## Usage

```bash
holiday-planner                    # opens the planner in the browser; Ctrl+C to stop
holiday-planner --port 9000 --no-open
holiday-planner --data /tmp/test-days.json   # use a scratch file, e.g. for testing
```

It is a small server on `127.0.0.1:8737`, reachable only from this machine. It rebuilds the
page on every load, so CONFIG edits show on refresh, and saves every booking to the
days-off file. There is no HTML file to open or publish.

No dependencies — Python 3 standard library only.

## Where the data lives

Booked and worked days are kept in `Notes/<year>/days-off-YYYY-yy.json` in the Holiday
Planning Dropbox folder, next to the ledger:

```json
{ "year": "2026-2027", "rev": 3, "booked": ["2026-12-07"], "worked": ["2026-09-11"] }
```

- `booked`: days off that use the allowance. Once a date has passed it counts as **taken**.
- `worked`: public holidays or weekends worked, each earning a Compensation Day.
- `rev` goes up on every save. The server refuses a save made against an older `rev`, so
  two open tabs cannot overwrite each other.

The file is plain JSON, so it can be edited by hand (or by Claude) while the server is
stopped. Test changes to the tool with `--data` pointing at a copy, never the real file.

## Updating it each July

Everything year-specific lives in the CONFIG block at the top of
`holiday-planner.py` and nowhere else. When the new calendars are published:

1. `PLANNING_YEAR` — September of the first year to August of the second.
2. `SCHOOL` — term dates, Christmas, Setmana Santa, lliure elecció days.
3. `UNI` — semester dates, assessment and resit periods, festius, ponts.
4. `RED_DAYS` — from the Generalitat labour calendar, plus Sabadell's two locals.
5. `PLAN` — the days off allocated in the annual HOLIDAYS ledgers.

Sources are listed under "Sources to Check Each Year" in the project's
`Notes/KEY CONCEPTS.md`. The school calendar is the binding constraint: it lands in
July, and the labour calendar runs about a year further ahead.

The run prints a day-count summary and the number of everyone-free stretches, which
is enough to sanity-check a new year's data.

### Install globally

```bash
ln -s /media/data/dev/bain-tools/holiday-planner/holiday-planner.py ~/.local/bin/holiday-planner
```
