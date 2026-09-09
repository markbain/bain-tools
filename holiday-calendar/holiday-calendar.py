#!/usr/bin/env python3
"""Build the Bain Family Holiday Calendar.

Overlays the children's school calendar and Alba's university calendar for one
planning year (September to August) and writes a self-contained HTML page showing
which days each part of the family is free — and, in gold, the days when everyone is.

    holiday-calendar                     # writes into the Holiday Planning project
    holiday-calendar -o /tmp/cal.html    # or anywhere else

By default it writes to the planning year's folder in the Holiday Planning Dropbox
project (see PROJECT below). Publish the resulting file as an Artifact to share it.

WHAT TO EDIT EACH JULY
----------------------
Everything year-specific lives in the CONFIG block below and nowhere else. When the
new calendars are published (see "Sources to Check Each Year" in Notes/KEY CONCEPTS.md):

  1. Set PLANNING_YEAR.
  2. Update SCHOOL   — term dates, Christmas, Setmana Santa, lliure elecció days.
  3. Update UNI      — semester dates, assessment and resit periods, festius, ponts.
  4. Update RED_DAYS — from the Generalitat labour calendar plus the two Sabadell locals.
  5. Update PLAN     — the days off allocated in the annual HOLIDAYS ledgers.

Then run it. No other part of the file should need touching.

Stdlib only, no dependencies.
"""

import argparse
import datetime as dt
import io
import os

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — the only part that changes from year to year
# ─────────────────────────────────────────────────────────────────────────────

PROJECT = "/media/data/Dropbox/Shared/Projects/Holiday Planning"

PLANNING_YEAR = (2026, 2027)          # September of the first year to August of the second

SCHOOL = {                            # Institut Vallès, Sabadell
    "term":            ("2026-09-08", "2027-06-21"),
    "christmas":       ("2026-12-22", "2027-01-07"),
    "setmana_santa":   ("2027-03-20", "2027-03-29"),
    "lliure_eleccio":  ["2026-10-30", "2026-11-20", "2026-12-07", "2027-02-08", "2027-04-30"],
}

UNI = {                               # Alba — Facultat de Belles Arts, UB
    "terms":       [("2026-09-14", "2027-01-19"), ("2027-02-08", "2027-06-04")],
    "assessment":  [("2027-01-08", "2027-01-19"), ("2027-05-24", "2027-06-04")],
    "admin":       [("2027-01-20", "2027-01-29"), ("2027-06-07", "2027-06-18")],
    "christmas":   ("2026-12-24", "2027-01-07"),
    "setmana_santa": ("2027-03-22", "2027-03-29"),
    "festius":     ["2026-09-11", "2026-10-12", "2026-11-01",
                    "2026-12-06", "2026-12-08", "2027-05-01", "2027-06-24"],
    "city":        ["2026-09-24", "2027-05-17"],      # Barcelona local holidays
    "non_teaching": ["2027-04-23"],                    # Sant Jordi
    "bridges":     ["2026-09-25", "2026-12-07"],       # ponts aprovats
}

RED_DAYS = {                          # public holidays, incl. the two Sabadell locals
    "2026-09-07": "Festa Major",        "2026-09-11": "Diada",
    "2026-10-12": "Hispanitat",         "2026-11-01": "All Saints",
    "2026-12-06": "Constitution Day",   "2026-12-08": "Immaculada",
    "2026-12-25": "Nadal (Christmas)",  "2026-12-26": "Sant Esteve",
    "2027-01-01": "New Year's Day",     "2027-01-06": "Reis (Epiphany)",
    "2027-03-26": "Good Friday",        "2027-03-29": "Easter Monday",
    "2027-05-01": "Labour Day",         "2027-05-10": "La Salut",
    "2027-06-24": "Sant Joan",          "2027-08-15": "L'Assumpció",
}
LOCAL_DAYS = ["2026-09-07", "2027-05-10"]     # Sabadell's two — drawn with a gold outline

PLAN = {                              # allocated days off, from the HOLIDAYS ledgers
    "2026-10-30": "½ hàbil",      "2026-12-07": "hàbil",
    "2026-12-22": "hàbil",        "2026-12-23": "hàbil",
    "2026-12-24": "recuperació",  "2026-12-28": "recuperació",
    "2026-12-29": "recuperació",  "2026-12-30": "recuperació",
    "2026-12-31": "recuperació",  "2027-01-04": "hàbil",
    "2027-01-05": "hàbil",        "2027-01-07": "hàbil",
    "2027-02-08": "hàbil",        "2027-03-22": "hàbil",
    "2027-03-23": "hàbil",        "2027-03-24": "hàbil",
    "2027-03-25": "hàbil",        "2027-04-30": "hàbil",
}

MIN_RUN = 3        # shortest everyone-free stretch worth listing

# ─────────────────────────────────────────────────────────────────────────────
# Logic — generic; should not need editing
# ─────────────────────────────────────────────────────────────────────────────

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
DOW = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

d = dt.date.fromisoformat


def span(pair):
    a, b = d(pair[0]), d(pair[1])
    out, x = set(), a
    while x <= b:
        out.add(x)
        x += dt.timedelta(days=1)
    return out


def spans(pairs):
    out = set()
    for p in pairs:
        out |= span(p)
    return out


def dates(seq):
    return {d(x) for x in seq}


def walk(a, b):
    x = a
    while x <= b:
        yield x
        x += dt.timedelta(days=1)


Y0, Y1 = PLANNING_YEAR
START, END = dt.date(Y0, 9, 1), dt.date(Y1, 8, 31)

RED = {d(k): v for k, v in RED_DAYS.items()}
LOCAL = dates(LOCAL_DAYS)
PLANNED = {d(k): v for k, v in PLAN.items()}

S_TERM = span(SCHOOL["term"])
S_FREE = span(SCHOOL["christmas"]) | span(SCHOOL["setmana_santa"])
S_LLIURE = dates(SCHOOL["lliure_eleccio"])

U_TERM = spans(UNI["terms"])
U_BUSY = spans(UNI["assessment"]) | spans(UNI["admin"])
U_FREE = span(UNI["christmas"]) | span(UNI["setmana_santa"])
U_DAYS = dates(UNI["festius"] + UNI["city"] + UNI["non_teaching"] + UNI["bridges"])
U_BRIDGE = dates(UNI["bridges"])


def school_free(x):
    if x.weekday() >= 5 or x in RED:
        return True
    if x not in S_TERM:
        return True
    return x in S_FREE or x in S_LLIURE


def uni_free(x):
    if x.weekday() >= 5 or x in U_DAYS or x in U_FREE:
        return True
    if x in U_BUSY:
        return False
    return x not in U_TERM


def category(x):
    if x in RED:
        return "red"
    if x.weekday() >= 5:
        return "wknd"
    s, u = school_free(x), uni_free(x)
    if s and u:
        return "all"
    if s:
        return "school"
    if u:
        return "uni"
    return "term"


def month_html(y, m):
    first = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), (m % 12) + 1, 1)
    cells = ['<div class="c pad"></div>'] * first.weekday()
    for x in walk(first, nxt - dt.timedelta(days=1)):
        cat = category(x)
        note = RED.get(x, "")
        if x in S_LLIURE:
            note = (note + " · " if note else "") + "lliure elecció"
        if x in U_BRIDGE and x not in S_LLIURE:
            note = (note + " · " if note else "") + "UB bridge day"
        if x in PLANNED:
            note = (note + " · " if note else "") + PLANNED[x]
        title = f'{x.isoformat()} — {note}' if note else x.isoformat()
        local = ' data-local="1"' if x in LOCAL else ""
        plan = " plan" if x in PLANNED else ""
        cells.append(f'<div class="c {cat}{plan}" title="{title}"{local}><span>{x.day}</span></div>')
    hdr = "".join(f'<div class="dow">{n}</div>' for n in DOW)
    return (f'<section class="mo"><h3>{MONTHS[m - 1]} <em>{y}</em></h3>'
            f'<div class="grid">{hdr}{"".join(cells)}</div></section>')


def everyone_free_runs():
    free = {x for x in walk(START, END) if school_free(x) and uni_free(x)}
    runs, cur = [], []
    for x in walk(START, END):
        if x in free:
            cur.append(x)
        else:
            if len(cur) >= MIN_RUN:
                runs.append((cur[0], cur[-1]))
            cur = []
    if len(cur) >= MIN_RUN:
        runs.append((cur[0], cur[-1]))
    return runs


def render():
    months, y, m = [], Y0, 9
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    grids = "\n".join(month_html(a, b) for a, b in months)

    rows = []
    for a, b in everyone_free_runs():
        label = (f"{a.day}–{b.day} {ABBR[a.month]}" if a.month == b.month
                 else f"{a.day} {ABBR[a.month]} – {b.day} {ABBR[b.month]}")
        rows.append(f'<tr><td class="w">{label}</td>'
                    f'<td class="n">{(b - a).days + 1}</td>'
                    f'<td class="yr">{a.year}</td></tr>')
    runs_html = "".join(rows)

    return f'''<title>Bain Family Holiday Calendar</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{{
  --paper:#FAF7F4; --card:#FFFFFF; --ink:#241F1D; --mute:#6E635E; --line:#E4DCD5;
  --red:#8E2230; --red-b:#8E2230; --red-t:#FFF6F2;
  --all:#A86512; --all-t:#FFF9EF;
  --school:#2F6B4F; --school-bg:#E4F0E8; --school-t:#1E4634;
  --uni:#2C5A8A; --uni-bg:#E3ECF5; --uni-t:#1D3E60;
  --wknd:#F1EBE5; --plan:#241F1D;
}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
  --paper:#17130F; --card:#211B17; --ink:#EFE7E0; --mute:#A3968D; --line:#3A302A;
  --red:#C4515F; --red-b:#7A1C28; --red-t:#FFEDEA;
  --all:#D89138; --all-t:#2A1B06;
  --school:#6FBF95; --school-bg:#1E3A2C; --school-t:#BFE6CF;
  --uni:#7FB0DE; --uni-bg:#1B3049; --uni-t:#C6DDF2;
  --wknd:#241E1A; --plan:#EFE7E0;
}}}}
:root[data-theme="dark"]{{
  --paper:#17130F; --card:#211B17; --ink:#EFE7E0; --mute:#A3968D; --line:#3A302A;
  --red:#C4515F; --red-b:#7A1C28; --red-t:#FFEDEA;
  --all:#D89138; --all-t:#2A1B06;
  --school:#6FBF95; --school-bg:#1E3A2C; --school-t:#BFE6CF;
  --uni:#7FB0DE; --uni-bg:#1B3049; --uni-t:#C6DDF2;
  --wknd:#241E1A; --plan:#EFE7E0;
}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:40px 24px 64px;display:flex;flex-direction:column;gap:32px}}
header{{display:flex;flex-direction:column;gap:6px;border-bottom:2px solid var(--ink);padding-bottom:18px}}
.eyebrow{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);font-weight:600}}
h1{{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:clamp(30px,5vw,46px);
  margin:0;line-height:1.05;text-wrap:balance;letter-spacing:-.01em}}
.sub{{color:var(--mute);max-width:64ch;font-size:14.5px}}
.top{{display:grid;grid-template-columns:1.35fr 1fr;gap:28px;align-items:start}}
@media (max-width:820px){{.top{{grid-template-columns:1fr}}}}
.key{{display:flex;flex-wrap:wrap;gap:7px}}
.k{{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--mute);
  border:1px solid var(--line);border-radius:999px;padding:4px 11px 4px 5px;background:var(--card)}}
.sw{{width:15px;height:15px;border-radius:4px;flex:none;border:1px solid rgba(0,0,0,.12)}}
h2{{font-family:Fraunces,Georgia,serif;font-size:17px;font-weight:600;margin:0 0 8px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
td{{padding:5px 0;border-bottom:1px solid var(--line)}}
td.n,td.yr{{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;text-align:right;color:var(--mute)}}
td.n{{width:3.2em}} td.yr{{width:4em}}
.cal{{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}}
@media (max-width:900px){{.cal{{grid-template-columns:repeat(2,1fr)}}}}
@media (max-width:520px){{.cal{{grid-template-columns:1fr}}}}
.mo h3{{font-family:Fraunces,Georgia,serif;font-size:14.5px;font-weight:600;margin:0 0 7px;
  letter-spacing:.01em}}
.mo h3 em{{font-style:normal;color:var(--mute);font-weight:400}}
.grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}}
.dow{{font-size:9.5px;letter-spacing:.06em;color:var(--mute);text-align:center;
  font-weight:600;padding-bottom:3px}}
.c{{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:4px;
  font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:11.5px;
  background:var(--card);border:1px solid var(--line);position:relative}}
.c.pad{{background:transparent;border-color:transparent}}
.c.wknd{{background:var(--wknd);border-color:transparent;color:var(--mute)}}
.c.term{{color:var(--mute)}}
.c.school{{background:var(--school-bg);border-color:transparent;color:var(--school-t);font-weight:500}}
.c.uni{{background:var(--uni-bg);border-color:transparent;color:var(--uni-t);font-weight:500}}
.c.all{{background:var(--all);border-color:transparent;color:var(--all-t);font-weight:500}}
.c.red{{background:var(--red-b);border-color:transparent;color:var(--red-t);font-weight:500}}
.c[data-local="1"]{{box-shadow:inset 0 0 0 2px var(--all)}}
.c.plan::after{{content:"";position:absolute;bottom:2.5px;width:4px;height:4px;border-radius:50%;
  background:var(--plan);opacity:.85}}
.c.all.plan::after,.c.red.plan::after{{background:var(--all-t)}}
footer{{border-top:1px solid var(--line);padding-top:16px;color:var(--mute);font-size:12.5px;
  display:flex;flex-direction:column;gap:7px}}
footer strong{{color:var(--ink);font-weight:600}}
a{{color:inherit}}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">Planning year 2026–27 · Sabadell &amp; Barcelona</div>
  <h1>Bain Family Holiday Calendar</h1>
  <p class="sub">The Institut Vallès and UB Belles Arts calendars overlaid, September 2026 to
  August 2027. Gold marks the working days when <em>everyone</em> is free — the only ones that
  count when booking a proper block.</p>
</header>

<div class="top">
  <div>
    <h2>Key</h2>
    <div class="key">
      <span class="k"><span class="sw" style="background:var(--red-b)"></span>Public holiday</span>
      <span class="k"><span class="sw" style="background:var(--all)"></span>Everyone free</span>
      <span class="k"><span class="sw" style="background:var(--school-bg)"></span>School only</span>
      <span class="k"><span class="sw" style="background:var(--uni-bg)"></span>Alba only (UB)</span>
      <span class="k"><span class="sw" style="background:var(--wknd)"></span>Weekend</span>
      <span class="k"><span class="sw" style="background:var(--card);border-color:var(--line)"></span>Term day</span>
    </div>
    <p class="sub" style="margin-top:12px">A dot under the figure marks a planned day off. A gold
    outline marks the two Sabadell local holidays. Hover any day for the detail.</p>
  </div>
  <div>
    <h2>Windows of 3 days or more</h2>
    <table><tbody>{runs_html}</tbody></table>
  </div>
</div>

<div class="cal">
{grids}
</div>

<footer>
  <div><strong>School</strong> Institut Vallès, Sabadell — term 8 Sep 2026 to 21 Jun 2027.
  Five lliure elecció days: 30 Oct, 20 Nov, 7 Dec, 8 Feb, 30 Apr. The published calendar is
  marked <em>previst</em> (provisional) and the regulations (Ordre EDF/66/2026) permit four —
  worth confirming with the school.</div>
  <div><strong>Alba</strong> Facultat de Belles Arts, UB — Q1 14 Sep to 19 Jan, Q2 8 Feb to
  4 Jun. Assessments 8–19 Jan and 24 May – 4 Jun; resits 28–29 Jan and 17–18 Jun. 7 December is
  an approved bridge day at Belles Arts too, so the whole family is free.</div>
  <div><strong>Mark's wife</strong> teaches in Sabadell, so her lliure elecció days match the
  children\'s.</div>
</footer>
</div>'''


def default_path():
    folder = os.path.join(PROJECT, "Notes", f"{Y0}-{Y1}")
    return os.path.join(folder, f"family-calendar-{Y0}-{str(Y1)[2:]}.html")


def main():
    parser = argparse.ArgumentParser(
        description="Build the Bain Family Holiday Calendar as a standalone HTML page."
    )
    parser.add_argument(
        "-o", "--output",
        help=f"Where to write the page (default: {default_path()})",
    )
    args = parser.parse_args()

    path = args.output or default_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    io.open(path, "w", encoding="utf-8").write(render())

    counts = {}
    for x in walk(START, END):
        counts[category(x)] = counts.get(category(x), 0) + 1
    print(f"wrote {path}")
    print(f"planning year {Y0}-{Y1}: " +
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"everyone-free runs of {MIN_RUN}+ days: {len(everyone_free_runs())}")


if __name__ == "__main__":
    main()
