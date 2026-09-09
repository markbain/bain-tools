# holiday-calendar

Builds the Bain Family Holiday Calendar: one HTML page overlaying the children's
school calendar and Alba's university calendar for a planning year, so you can see
at a glance who is free when.

Gold marks the working days when *everyone* is free, which are the only ones that
count when booking a proper block. Maroon is a public holiday, pale green a
school-only day, pale blue a university-only day.

## Usage

```bash
# Write into the Holiday Planning project (the default)
holiday-calendar

# Or anywhere else
holiday-calendar -o /tmp/calendar.html
```

Then publish the file as an Artifact to share it with the family.

No dependencies — Python 3 standard library only.

## Updating it each July

Everything year-specific lives in the CONFIG block at the top of
`holiday-calendar.py` and nowhere else. When the new calendars are published:

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
ln -s /media/data/dev/bain-tools/holiday-calendar/holiday-calendar.py ~/.local/bin/holiday-calendar
```
