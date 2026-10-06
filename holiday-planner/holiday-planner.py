#!/usr/bin/env python3
"""Mark's holiday planner, whose goal is to help him pick the best days to take off.

Overlays the children's school calendar and Alba's university calendar for one
planning year (September to August), showing which days each part of the family is
free, and keeps track of the days he books, takes and works.

    holiday-planner                      # run it: opens in the browser on 127.0.0.1:8737
    holiday-planner --port 9000 --no-open

A small local server, not a published page. It rebuilds the page on every load and
saves bookings to the days-off JSON file in the planning year's Dropbox folder.

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
import http.server
import io
import json
import os
import threading
import webbrowser

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
    "2026-10-30": "hàbil",        "2026-11-20": "hàbil",
    "2026-12-07": "hàbil",
    "2026-12-22": "hàbil",        "2026-12-23": "hàbil",
    "2026-12-24": "recuperació",  "2026-12-28": "recuperació",
    "2026-12-29": "recuperació",  "2026-12-30": "recuperació",
    "2026-12-31": "recuperació",  "2027-01-04": "hàbil",
    "2027-01-05": "hàbil",        "2027-01-07": "hàbil",
    "2027-02-08": "hàbil",        "2027-03-22": "hàbil",
    "2027-03-23": "hàbil",        "2027-03-24": "hàbil",
    "2027-03-25": "hàbil",        "2027-04-30": "hàbil",
}

MUSIC_CLASHES = {                     # holidays that still have music classes that evening
    "2026-10-30": "4 classes, 19:00–21:15",
    "2026-11-20": "4 classes, 19:00–21:15",
    "2027-02-08": "5 classes, 18:30–21:15",
    "2027-04-30": "4 classes, 19:00–21:15",
}

# One entitlement year, matching the planning year: 1 Sept to 31 Aug. Re-based from the
# calendar year on 2026-09-09 — see "The Planning Year" in Notes/KEY CONCEPTS.md.
ENTITLEMENT = {
    "2026-2027": {"habils": 22, "habils_taken": 0, "recovery": 5, "recovery_taken": 0},
}

PUBLIC_HOLIDAYS = 16                  # 14 national/regional + 2 Sabadell local


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
CLASHES = {d(k): v for k, v in MUSIC_CLASHES.items()}

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
    if x in LOCAL:
        return "local"
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
        if x in CLASHES:
            note = (note + " · " if note else "") + "MUSIC: " + CLASHES[x]
        title = f'{x.isoformat()} — {note}' if note else x.isoformat()
        plan = " plan" if x in PLANNED else ""
        clash = " clash" if x in CLASHES else ""
        if cat in ("red", "local"):
            book = ' data-work="1"' if x.weekday() < 5 else ''
        elif cat == "wknd":
            book = ' data-work="1"'
        else:
            book = ' data-book="1"'
        cells.append(f'<div class="c {cat}{plan}{clash}" title="{title}" '
                     f'data-date="{x.isoformat()}"{book}><span>{x.day}</span></div>')
    hdr = "".join(f'<div class="dow">{n}</div>' for n in DOW)
    return (f'<section class="mo" data-name="{MONTHS[m - 1]} {y}"><h3>{MONTHS[m - 1]} <em>{y}</em></h3>'
            f'<div class="grid">{hdr}{"".join(cells)}</div></section>')


CSS = """
:root{
  color-scheme:light;
  --paper:#FAF8F5; --card:#FFFFFF; --ink:#241F1D; --mute:#6E635E; --line:#DFD7CF;
  --red-b:#A32D35; --red-t:#FFF1EF;
  --school-bg:#F3D79B; --school-t:#63450F;
  --uni-bg:#B7D3EE; --uni-t:#1A3D61;
  --wknd:#E7E2DB; --local:#7A2E6A; --local-t:#FCEEF7;
  --ok:#2F6B45;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --paper:#16120F; --card:#221D18; --ink:#EFE7E0; --mute:#A3968D; --line:#3C322B;
  --red-b:#96303A; --red-t:#FFE7E4;
  --school-bg:#7A5A1E; --school-t:#F7E2B4;
  --uni-bg:#2B4C70; --uni-t:#D3E6F8;
  --wknd:#282119; --local:#8C3A78; --local-t:#FBE3F3;
  --ok:#7CC294;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --paper:#16120F; --card:#221D18; --ink:#EFE7E0; --mute:#A3968D; --line:#3C322B;
  --red-b:#96303A; --red-t:#FFE7E4;
  --school-bg:#7A5A1E; --school-t:#F7E2B4;
  --uni-bg:#2B4C70; --uni-t:#D3E6F8;
  --wknd:#282119; --local:#8C3A78; --local-t:#FBE3F3;
  --ok:#7CC294;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 "IBM Plex Sans",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
.mono{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.wrap{max-width:1280px;margin:0 auto;padding:28px 32px 56px}
@media (max-width:700px){.wrap{padding:20px 16px 40px}}

/* Header and tabs */
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:12px 20px;flex-wrap:wrap;
  padding-bottom:14px;border-bottom:2px solid var(--ink)}
.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);font-weight:600}
h1{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:clamp(26px,4vw,36px);margin:2px 0 0;
  line-height:1.05;letter-spacing:-.01em}
h2{font-family:Fraunces,Georgia,serif;font-size:17px;font-weight:600;margin:0 0 6px}
.summary{display:flex;gap:6px;flex-wrap:wrap}
.pill{font-size:12px;border:1px solid var(--line);background:var(--card);border-radius:999px;
  padding:4px 11px;color:var(--mute)}
.pill b{font-family:"IBM Plex Mono",monospace;font-weight:500;color:var(--ink)}
.pill.status::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;
  margin-right:6px;background:var(--mute);vertical-align:1px}
.pill.status.live::before{background:var(--ok)}
.pill.status.error::before{background:var(--red-b)}
.notice{font-size:13px;color:var(--ink);background:var(--card);border:1px solid var(--line);
  border-left:4px solid var(--mute);border-radius:8px;padding:10px 12px;margin:0 0 18px}
.notice[hidden]{display:none}
.notice code{font-family:"IBM Plex Mono",monospace;font-size:12px}
.tabs{display:flex;gap:2px;margin:16px 0 22px;box-shadow:inset 0 -1px 0 var(--line);
  overflow-x:auto;overflow-y:hidden;scrollbar-width:none}
.tab{font:inherit;font-size:14px;font-weight:500;color:var(--mute);background:none;border:0;
  padding:9px 16px;cursor:pointer;white-space:nowrap}
.tab:hover{color:var(--ink)}
.tab[aria-selected="true"]{color:var(--ink);box-shadow:inset 0 -2px 0 var(--ink)}
.tab:focus-visible,.seg button:focus-visible,select:focus-visible,.pick:focus-visible,
button.chip:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.panel[hidden]{display:none}
.hint{font-size:12.5px;color:var(--mute);margin:0}

/* Controls */
.toolbar{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;margin-bottom:16px}
.field{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;color:var(--mute)}
select{font:inherit;font-size:13px;color:var(--ink);background:var(--card);border:1px solid var(--line);
  border-radius:6px;padding:5px 8px;cursor:pointer}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden;background:var(--card)}
.seg button{font:inherit;font-size:12.5px;border:0;background:none;color:var(--mute);padding:6px 13px;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.check{display:inline-flex;gap:6px;align-items:center;font-size:12.5px;color:var(--mute);cursor:pointer}
input[type=checkbox]{accent-color:var(--ink);margin:0}

/* Days off */
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:22px}
@media (max-width:800px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.stat .v{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:24px;line-height:1.15}
.stat .v small{font-size:13px;color:var(--mute);margin-left:4px}
.stat .l{font-size:12px;color:var(--mute)}
.breaks{display:flex;flex-direction:column;gap:6px;max-width:900px}
.mhead{font-family:Fraunces,Georgia,serif;font-size:15px;font-weight:600;margin:16px 0 2px}
.mhead:first-child{margin-top:0}
.brk{display:grid;grid-template-columns:minmax(170px,1.3fr) 64px minmax(0,2.2fr) 92px;gap:6px 14px;
  align-items:center;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--red-b);
  border-radius:8px;padding:10px 12px}
.brk.mine{border-left-color:var(--ink)}
.brk.past{opacity:.6}
.brk .when{font-weight:600}
.brk .len,.brk .cost{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--mute)}
.brk .cost{text-align:right}
.brk .days{display:flex;flex-wrap:wrap;gap:4px}
@media (max-width:700px){.brk{grid-template-columns:1fr auto}.brk .days{grid-column:1/-1}
  .brk .cost{grid-column:1/-1;text-align:left}}
.chip{display:inline-flex;align-items:center;gap:5px;font-family:"IBM Plex Mono",monospace;font-size:11px;
  border:1px solid var(--line);background:var(--paper);border-radius:5px;padding:2px 7px;color:var(--ink)}
.chip i{width:8px;height:8px;border-radius:2px;flex:none}
.chip i.booked{background:var(--ink)}
.chip i.taken{background:var(--ok)}
.chip i.red{background:var(--red-b)}
.chip i.local{background:var(--local)}
.chip i.wknd{background:var(--wknd);border:1px solid var(--line)}
button.chip{cursor:pointer}
button.chip:hover{border-color:var(--red-b);color:var(--red-b)}
button.chip .x{opacity:.55}
.tag{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);
  margin-left:6px}
.tag.taken{color:var(--ok)}
.empty{font-size:13px;color:var(--mute);padding:16px;border:1px dashed var(--line);border-radius:8px;
  max-width:900px}

/* Plan */
.plan-cols{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}
@media (max-width:1000px){.plan-cols{grid-template-columns:1fr}}
.cal{display:grid;grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:18px}
.cal.one{grid-template-columns:minmax(0,420px)}
.cal.one .c{font-size:14px}
.mo[hidden]{display:none}
.mo h3{font-family:Fraunces,Georgia,serif;font-size:14.5px;font-weight:600;margin:0 0 7px}
.mo h3 em{font-style:normal;color:var(--mute);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.dow{font-size:9.5px;letter-spacing:.06em;color:var(--mute);text-align:center;font-weight:600;padding-bottom:3px}
.c{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:4px;
  font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:11.5px;font-weight:500;
  background:var(--card);border:1px solid var(--line);position:relative}
.c.pad{background:transparent;border-color:transparent}
.c.wknd{background:var(--wknd);border-color:transparent;color:var(--mute);font-weight:400}
.c.term{color:var(--mute);font-weight:400}
.c.school{background:var(--school-bg);border-color:transparent;color:var(--school-t);font-weight:600}
.c.uni{background:var(--uni-bg);border-color:transparent;color:var(--uni-t);font-weight:600}
.c.all{background:linear-gradient(135deg,var(--school-bg) 0 50%,var(--uni-bg) 50% 100%);border-color:transparent;
  color:var(--ink);font-weight:600}
.c.red{background:var(--red-b);border-color:transparent;color:var(--red-t);font-weight:600}
.c.local{background:var(--local);border-color:transparent;color:var(--local-t);font-weight:600}
.c.plan::after{content:"";position:absolute;bottom:2.5px;width:4px;height:4px;border-radius:50%;
  background:currentColor;opacity:.9}
.c.clash::before{content:"";position:absolute;top:2.5px;width:9px;height:2px;border-radius:1px;
  background:currentColor;opacity:.75}
.cal.no-plan .c.plan::after,.cal.no-clash .c.clash::before{content:none}
.c[data-book],.c[data-work]{cursor:pointer}
.c[data-book]:hover,.c[data-work]:hover{box-shadow:inset 0 0 0 2px var(--mute)}
.c.booked{box-shadow:inset 0 0 0 2.5px var(--ink)}
.c.booked span{text-decoration:underline;text-underline-offset:2px}
.c.booked.past{box-shadow:inset 0 0 0 2.5px var(--ok)}
.c.past{opacity:.45}
.c.past.booked{opacity:.8}
.c.today{outline:2px solid var(--ink);outline-offset:1px;z-index:1}
.c.run{box-shadow:inset 0 0 0 2px var(--ink);opacity:1}
.c.worked{background:var(--card);color:var(--red-b);box-shadow:inset 0 0 0 1.5px var(--red-b)}
.c.local.worked{color:var(--local);box-shadow:inset 0 0 0 1.5px var(--local)}
.c.wknd.worked{color:var(--mute);box-shadow:inset 0 0 0 1.5px var(--mute)}
.c.worked span{text-decoration:line-through;text-decoration-thickness:1.5px}
details.key{margin:-6px 0 16px}
details.key summary{cursor:pointer;font-size:12.5px;color:var(--mute);width:max-content}
.keyrow{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.k{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--mute);
  border:1px solid var(--line);border-radius:999px;padding:3px 10px 3px 4px;background:var(--card)}
.sw{width:15px;height:15px;border-radius:4px;flex:none;border:1px solid rgba(0,0,0,.12)}
.side-panel{position:sticky;top:16px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
@media (max-width:1000px){.side-panel{position:static}}
.best-filters{display:flex;flex-direction:column;gap:8px;margin:12px 0}
.best-filters .field{justify-content:space-between}
.best{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:5px}
.pick{width:100%;display:grid;grid-template-columns:auto 1fr auto;gap:2px 8px;align-items:baseline;text-align:left;
  font:inherit;font-size:12.5px;color:var(--ink);background:var(--paper);border:1px solid var(--line);
  border-radius:6px;padding:7px 9px;cursor:pointer}
.pick:hover{border-color:var(--ink)}
.pick .day{font-weight:600}
.pick .len{font-family:"IBM Plex Mono",monospace;font-size:12px;justify-self:end}
.pick .why{grid-column:1/-1;font-size:11px;color:var(--mute)}

/* Allowance */
.allow-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;max-width:1200px;margin-bottom:16px;
  align-items:start}
@media (max-width:1000px){.allow-cols{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:700px){.allow-cols{grid-template-columns:1fr}}
.rec{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}
.rec li{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:5px 0;
  border-bottom:1px solid var(--line)}
.rec li:last-child{border-bottom:0}
.rec .dt{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--mute);white-space:nowrap}
.warn{color:var(--red-b)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.big{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;font-size:34px;line-height:1}
.bar{height:6px;border-radius:3px;background:var(--wknd);margin:12px 0 10px;overflow:hidden;display:flex}
.bar i{display:block;height:100%}
.bar i.taken{background:var(--ok)}
.bar i.booked{background:var(--ink)}
.bar.over i.booked{background:var(--red-b)}
.rows{display:flex;flex-direction:column;gap:2px}
.row{display:flex;justify-content:space-between;font-size:13px;color:var(--mute)}
.row b{font-family:"IBM Plex Mono",monospace;font-weight:500;color:var(--ink)}
.row.total{border-top:1px solid var(--line);margin-top:4px;padding-top:4px;color:var(--ink);font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.rules{max-width:1200px;font-size:13px;color:var(--mute)}
.rules p{margin:8px 0 0}
.rules b{color:var(--ink)}
"""

BODY = """<div class="wrap">
<header class="top">
  <div>
    <div class="eyebrow">Planning year __PYL__</div>
    <h1>Holiday Planner</h1>
  </div>
  <div class="summary" id="summary"></div>
</header>

<nav class="tabs" role="tablist">
  <button class="tab" role="tab" data-tab="off" aria-controls="p-off">Days off</button>
  <button class="tab" role="tab" data-tab="plan" aria-controls="p-plan">Plan</button>
  <button class="tab" role="tab" data-tab="allow" aria-controls="p-allow">Allowance</button>
</nav>

<p class="notice" id="notice" hidden></p>

<section class="panel" id="p-off" role="tabpanel">
  <div class="stats" id="stats"></div>
  <div class="toolbar">
    <div class="seg" role="group" aria-label="When">
      <button data-ui="when" data-val="upcoming">Upcoming</button>
      <button data-ui="when" data-val="past">Taken</button>
      <button data-ui="when" data-val="all">Whole year</button>
    </div>
    <label class="field">Show
      <select data-ui="show">
        <option value="all">All breaks</option>
        <option value="mine">Breaks using my days</option>
        <option value="hols">Public holidays only</option>
      </select>
    </label>
  </div>
  <div class="breaks" id="breaks"></div>
</section>

<section class="panel" id="p-plan" role="tabpanel">
  <div class="toolbar">
    <label class="field">Months <select data-ui="months" id="months"></select></label>
    <label class="check"><input type="checkbox" data-ui="plan"> Suggested plan</label>
    <label class="check"><input type="checkbox" data-ui="clash"> Music classes</label>
  </div>
  <details class="key">
    <summary>Key</summary>
    <div class="keyrow">
      <span class="k"><span class="sw" style="background:linear-gradient(135deg,var(--school-bg) 0 50%,var(--uni-bg) 50% 100%)"></span>Everyone free</span>
      <span class="k"><span class="sw" style="background:var(--school-bg)"></span>School free, Alba busy</span>
      <span class="k"><span class="sw" style="background:var(--uni-bg)"></span>Only Alba free</span>
      <span class="k"><span class="sw" style="background:var(--red-b)"></span>National holiday</span>
      <span class="k"><span class="sw" style="background:var(--local)"></span>Sabadell holiday</span>
      <span class="k"><span class="sw" style="background:var(--wknd)"></span>Weekend</span>
      <span class="k"><span class="sw" style="background:var(--card);box-shadow:inset 0 0 0 2px var(--ink)"></span>Booked</span>
      <span class="k"><span class="sw" style="background:var(--card);box-shadow:inset 0 0 0 2px var(--ok)"></span>Taken</span>
      <span class="k"><span class="sw" style="background:var(--card);box-shadow:inset 0 0 0 1.5px var(--red-b)"></span>Worked (Compensation Day)</span>
    </div>
  </details>
  <div class="plan-cols">
    <main class="cal" id="cal">
__GRIDS__
    </main>
    <aside class="side-panel">
      <h2>Best days</h2>
      <p class="hint">Ranked by the unbroken break each day would give you. Hover to see the break,
      click to book.</p>
      <div class="best-filters">
        <label class="field">Who must be free
          <select data-ui="who">
            <option value="core">School side</option>
            <option value="everyone">Everyone, Alba too</option>
          </select>
        </label>
        <label class="field">Break of at least
          <select data-ui="min">
            <option value="1">any length</option>
            <option value="3">3 days</option>
            <option value="4">4 days</option>
            <option value="5">5 days</option>
          </select>
        </label>
        <label class="check"><input type="checkbox" data-ui="noclash"> Skip music-class days</label>
      </div>
      <ol class="best" id="best"></ol>
    </aside>
  </div>
  <p class="hint" style="margin-top:16px">Click a working day to book it, and again to release it.
  Click a public holiday or a weekend you worked to earn a Compensation Day.</p>
</section>

<section class="panel" id="p-allow" role="tabpanel">
  <div class="allow-cols">
    <div class="card" id="poolcard"></div>
    <div class="card" id="reccard"></div>
    <div class="card">
      <h2>Compensation Days</h2>
      <p class="hint">Each public holiday or weekend you work earns a Compensation Day to take later. Mark a day as worked on the Plan tab; click it here to undo.</p>
      <div class="chips" id="wlist"></div>
    </div>
  </div>
  <div class="card rules">
    <h2>How the allowance works</h2>
    <p><b>38 days a year.</b> 16 public holidays (14 national and regional, plus Sabadell's two)
    and <b>22 hàbils</b>, the working days you choose. Public holidays cost nothing; only hàbils
    are spent.</p>
    <p><b>A public holiday on a weekend earns a Recovery Day</b>, a working day to take whenever
    you like. This holds even when the Generalitat drops that holiday from its published
    calendar, as it does when one falls on a Sunday.</p>
    <p><b>Working a day you would otherwise have off earns a Compensation Day.</b></p>
    <p><b>Booked</b> days are still ahead; once the date passes they count as <b>taken</b>. If you
    end up working a day you had booked, release it and it goes back into the allowance.</p>
    <p>The year runs <b>1 September to 31 August</b>. Days must be used by 31 August; nothing
    carries over.</p>
  </div>
</section>
</div>"""

SCRIPT = """<script>
(function () {
  var POOLS = __POOLS__;
  var RECOVERY = __RECOVERY__;   // public holidays on a weekend, each earning a Recovery Day
  var YEAR = Object.keys(POOLS)[0];
  var UI_KEY = "holiday-planner:ui";
  // Days off live in a JSON file next to the ledger. The server builds the page with the
  // file's current contents and saves every change back to it through /api/days.
  var DATA = __DATA__;
  var booked = new Set(DATA.booked);
  var worked = new Set(DATA.worked);
  var rev = DATA.rev;
  var mode = "live";          // live · saving · error

  var cells = {};
  document.querySelectorAll(".c[data-date]").forEach(function (el) { cells[el.dataset.date] = el; });
  var DAYS = Object.keys(cells).sort();
  var IDX = {};
  DAYS.forEach(function (d, i) { IDX[d] = i; });
  var MONTHS = Array.from(document.querySelectorAll(".mo"));

  var DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var MONTH = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"];

  function has(d, c) { return !!cells[d] && cells[d].classList.contains(c); }
  function costs(d) { return !!cells[d] && cells[d].hasAttribute("data-book"); }
  function workable(d) { return !!cells[d] && cells[d].hasAttribute("data-work"); }
  function isHol(d) { return has(d, "red") || has(d, "local"); }
  function holName(d) { var t = cells[d].title.split(" — ")[1] || ""; return t.split(" · ")[0]; }
  function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
  function label(d, withDay) {
    var x = new Date(d + "T12:00:00");
    return (withDay ? DOW[x.getDay()] + " " : "") + x.getDate() + " " + MON[x.getMonth()];
  }
  function iso(t) {
    return t.getFullYear() + "-" + String(t.getMonth() + 1).padStart(2, "0") + "-" +
      String(t.getDate()).padStart(2, "0");
  }
  var TODAY = iso(new Date());
  function daysUntil(d) {
    return Math.round((new Date(d + "T12:00:00") - new Date(TODAY + "T12:00:00")) / 864e5);
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // A day is off if booked, or a weekend or public holiday that was not worked.
  function off(d) {
    if (booked.has(d)) return true;
    if (worked.has(d)) return false;
    return has(d, "wknd") || isHol(d);
  }

  // ── View state: remembered per browser, harmless if storage is unavailable ──
  var ui = { tab: "off", when: "upcoming", show: "all", months: "all", plan: true, clash: true,
             who: "core", min: "1", noclash: false };
  try {
    var savedUi = JSON.parse(localStorage.getItem(UI_KEY) || "null");
    if (savedUi) Object.keys(ui).forEach(function (k) { if (k in savedUi) ui[k] = savedUi[k]; });
  } catch (err) {}
  function saveUi() { try { localStorage.setItem(UI_KEY, JSON.stringify(ui)); } catch (err) {} }

  // ── Allowance ──
  function pool() {
    var p = POOLS[YEAR], taken = 0, ahead = 0, comp = 0;
    booked.forEach(function (d) { if (costs(d)) { if (d < TODAY) taken++; else ahead++; } });
    worked.forEach(function (d) { if (workable(d)) comp++; });
    var total = (p.habils - p.habilsTaken) + (p.recovery - p.recoveryTaken) + comp;
    return { p: p, taken: taken + p.habilsTaken + p.recoveryTaken, ahead: ahead, comp: comp,
             total: total + p.habilsTaken + p.recoveryTaken, left: total - taken - ahead };
  }

  // ── Breaks: unbroken runs of days off that include at least one working day off ──
  function breaks() {
    var runs = [], cur = null;
    DAYS.forEach(function (d) {
      if (off(d)) { (cur = cur || []).push(d); } else if (cur) { runs.push(cur); cur = null; }
    });
    if (cur) runs.push(cur);
    return runs.map(function (run) {
      var b = { from: run[0], to: run[run.length - 1], len: run.length, mine: [], hols: [] };
      run.forEach(function (d) {
        if (booked.has(d)) b.mine.push(d);
        else if (isHol(d) && workable(d)) b.hols.push(d);
      });
      return b;
    }).filter(function (b) { return b.mine.length + b.hols.length > 0; });
  }

  function renderSummary(pl) {
    var st = { live: ["live", "Saved"], saving: ["", "Saving…"],
               error: ["error", "Not saved"] }[mode];
    document.getElementById("summary").innerHTML =
      '<span class="pill status ' + st[0] + '">' + st[1] + '</span>' +
      '<span class="pill"><b>' + pl.left + '</b> left to place</span>';
  }

  function renderOff(pl, all) {
    var next = all.filter(function (b) { return b.from > TODAY; })[0];
    var stats = [
      [pl.taken + '<small>' + (pl.taken === 1 ? "day" : "days") + '</small>', "Taken from the allowance"],
      [pl.ahead + '<small>' + (pl.ahead === 1 ? "day" : "days") + '</small>', "Booked ahead"],
      [pl.left + '<small>of ' + pl.total + '</small>', "Still to place"],
      [next ? daysUntil(next.from) + '<small>' + (daysUntil(next.from) === 1 ? "day" : "days") + '</small>' : "–",
       next ? "Until the next break, " + label(next.from, true) : "No break booked ahead"]
    ];
    document.getElementById("stats").innerHTML = stats.map(function (s) {
      return '<div class="stat"><div class="v">' + s[0] + '</div><div class="l">' + esc(s[1]) + '</div></div>';
    }).join("");

    var bs = all.filter(function (b) {
      if (ui.when === "upcoming" && b.to < TODAY) return false;
      if (ui.when === "past" && b.from >= TODAY) return false;
      if (ui.show === "mine" && !b.mine.length) return false;
      if (ui.show === "hols" && b.mine.length) return false;
      return true;
    });
    var box = document.getElementById("breaks");
    if (!bs.length) {
      box.innerHTML = '<div class="empty">' + (ui.when === "past" ? "Nothing taken yet." :
        "Nothing to show. Book days from the Plan tab.") + '</div>';
      return;
    }
    var html = "", month = "";
    bs.forEach(function (b) {
      var x = new Date(b.from + "T12:00:00"), m = MONTH[x.getMonth()] + " " + x.getFullYear();
      if (m !== month) { html += '<div class="mhead">' + m + '</div>'; month = m; }
      var past = b.to < TODAY, now = b.from <= TODAY && !past;
      var when = b.from === b.to ? label(b.from, true) : label(b.from, true) + " – " + label(b.to, true);
      var tag = past ? '<span class="tag taken">taken</span>' : now ? '<span class="tag">now</span>' : "";
      var chips = b.mine.concat(b.hols).sort().map(function (d) {
        if (booked.has(d)) {
          var t = d < TODAY;
          return '<button class="chip" data-rm="' + d + '" title="' + (t ? "Taken. Click if you " +
            "worked it after all, to return it to the allowance" : "Booked. Click to release") + '">' +
            '<i class="' + (t ? "taken" : "booked") + '"></i>' + label(d, true) +
            ' <span class="x">×</span></button>';
        }
        return '<span class="chip" title="' + esc(holName(d)) + '"><i class="' +
          (has(d, "local") ? "local" : "red") + '"></i>' + label(d, true) + " · " + esc(holName(d)) + '</span>';
      }).join("");
      var n = b.mine.length;
      html += '<div class="brk' + (n ? " mine" : "") + (past ? " past" : "") + '">' +
        '<div class="when">' + when + tag + '</div>' +
        '<div class="len">' + plural(b.len, "day") + '</div>' +
        '<div class="days">' + chips + '</div>' +
        '<div class="cost">' + (n ? (past ? "used " : "uses ") + n : "free") + '</div></div>';
    });
    box.innerHTML = html;
  }

  // ── Plan: calendar and best days ──
  function renderMonths() {
    var sel = document.getElementById("months");
    if (!sel.options.length) {
      var opts = [["all", "Whole year"], ["0-3", "Sep – Dec"], ["4-7", "Jan – Apr"], ["8-11", "May – Aug"]];
      MONTHS.forEach(function (s, i) { opts.push([String(i), s.dataset.name]); });
      sel.innerHTML = opts.map(function (o) {
        return '<option value="' + o[0] + '">' + o[1] + '</option>'; }).join("");
    }
    var lo = 0, hi = 11;
    if (ui.months !== "all") {
      var parts = ui.months.split("-");
      lo = +parts[0]; hi = parts.length > 1 ? +parts[1] : lo;
    }
    MONTHS.forEach(function (s, i) { s.hidden = i < lo || i > hi; });
    var cal = document.getElementById("cal");
    cal.classList.toggle("one", lo === hi);
    cal.classList.toggle("no-plan", !ui.plan);
    cal.classList.toggle("no-clash", !ui.clash);
  }

  function runAround(d) {
    var i = IDX[d], l = i, r = i;
    while (l > 0 && off(DAYS[l - 1])) l--;
    while (r < DAYS.length - 1 && off(DAYS[r + 1])) r++;
    return { from: DAYS[l], to: DAYS[r], len: r - l + 1 };
  }

  // Each open day the family is free is scored by the unbroken break it would create. Ties go
  // to days when everyone is free, then to days with no music class, then to the earliest.
  function renderBest(pl) {
    var box = document.getElementById("best");
    if (pl.left <= 0) { box.innerHTML = '<li class="hint">No days left to place.</li>'; return; }
    var min = +ui.min;
    var picks = DAYS.filter(function (d) {
      if (d < TODAY || !costs(d) || booked.has(d)) return false;
      if (ui.noclash && has(d, "clash")) return false;
      return has(d, "all") || (ui.who === "core" && has(d, "school"));
    }).map(function (d) {
      return { d: d, run: runAround(d), all: has(d, "all"), clash: has(d, "clash") };
    }).filter(function (p) { return p.run.len >= min; }).sort(function (a, b) {
      return (b.run.len - a.run.len) || (b.all - a.all) || (a.clash - b.clash) || (a.d < b.d ? -1 : 1);
    }).slice(0, 10);
    if (!picks.length) { box.innerHTML = '<li class="hint">Nothing matches these filters.</li>'; return; }
    box.innerHTML = picks.map(function (p) {
      var span = p.run.from === p.run.to ? "just the day" : label(p.run.from) + " – " + label(p.run.to);
      var who = p.all ? "everyone free" : "school free, Alba busy";
      return '<li><button class="pick" data-pick="' + p.d + '" data-from="' + p.run.from +
        '" data-to="' + p.run.to + '"><span class="day">' + label(p.d, true) + '</span><span>' + span +
        '</span><span class="len">' + plural(p.run.len, "day") + '</span><span class="why">' + who +
        (p.clash ? " · music class that evening" : "") + '</span></button></li>';
    }).join("");
  }

  function renderCells() {
    Object.keys(cells).forEach(function (d) {
      var el = cells[d];
      el.classList.toggle("booked", booked.has(d));
      el.classList.toggle("worked", worked.has(d));
      el.classList.toggle("past", d < TODAY);
      el.classList.toggle("today", d === TODAY);
      el.classList.remove("run");
    });
  }

  // ── Allowance tab ──
  function renderRecovery(pl) {
    var html = '<h2>Recovery Days</h2>' +
      '<p class="hint">Public holidays that fall on a weekend this year. Each one earns a ' +
      'Recovery Day to take on a working day instead.</p>' +
      '<ul class="rec">' + RECOVERY.map(function (r) {
        return '<li><span>' + esc(r.name) + '</span><span class="dt">' + label(r.date, true) + '</span></li>';
      }).join("") + '</ul>' +
      '<div class="rows" style="margin-top:10px"><div class="row total"><span>Recovery Days earned</span><b>' +
      RECOVERY.length + '</b></div></div>';
    if (RECOVERY.length !== pl.p.recovery) {
      html += '<p class="hint warn" style="margin-top:8px">The allowance is set to ' + pl.p.recovery +
        ' Recovery Days but the calendar has ' + RECOVERY.length + '. Check ENTITLEMENT in the script.</p>';
    }
    document.getElementById("reccard").innerHTML = html;
  }

  function renderAllowance(pl) {
    renderRecovery(pl);
    var pct = function (n) { return pl.total ? Math.min(100, n / pl.total * 100) : 0; };
    document.getElementById("poolcard").innerHTML =
      '<h2>' + YEAR + '</h2>' +
      '<div class="big">' + pl.left + '</div><div class="hint">days still to place</div>' +
      '<div class="bar' + (pl.left < 0 ? " over" : "") + '"><i class="taken" style="width:' +
      pct(pl.taken) + '%"></i><i class="booked" style="width:' + pct(pl.ahead) + '%"></i></div>' +
      '<div class="rows">' +
      '<div class="row"><span>Hàbils</span><b>' + pl.p.habils + '</b></div>' +
      '<div class="row"><span>Recovery days</span><b>' + pl.p.recovery + '</b></div>' +
      '<div class="row"><span>Compensation days</span><b>' + pl.comp + '</b></div>' +
      '<div class="row total"><span>Allowance</span><b>' + pl.total + '</b></div>' +
      '<div class="row"><span>Taken</span><b>' + pl.taken + '</b></div>' +
      '<div class="row"><span>Booked ahead</span><b>' + pl.ahead + '</b></div>' +
      '<div class="row total"><span>Still to place</span><b>' + pl.left + '</b></div>' +
      '</div>';
    var w = Array.from(worked).sort();
    document.getElementById("wlist").innerHTML = w.length ? w.map(function (d) {
      return '<button class="chip" data-rm="' + d + '" title="Worked this day. Click to undo"><i class="' +
        (has(d, "wknd") ? "wknd" : has(d, "local") ? "local" : "red") + '"></i>' + label(d, true) +
        ' <span class="x">×</span></button>';
    }).join("") : '<span class="hint">None earned yet.</span>';
  }

  function renderControls() {
    document.querySelectorAll(".tab").forEach(function (t) {
      var on = t.dataset.tab === ui.tab;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    document.querySelectorAll("[data-ui]").forEach(function (el) {
      var k = el.dataset.ui;
      if (el.tagName === "BUTTON") el.setAttribute("aria-pressed", ui[k] === el.dataset.val);
      else if (el.type === "checkbox") el.checked = !!ui[k];
      else el.value = ui[k];
    });
  }

  function render() {
    var pl = pool(), bs = breaks();
    renderMonths();
    renderControls();
    renderCells();
    renderSummary(pl);
    renderOff(pl, bs);
    renderBest(pl);
    renderAllowance(pl);
  }

  // ── Bookings, stored in the days-off file ──
  function notice(html) {
    var el = document.getElementById("notice");
    el.innerHTML = html || "";
    el.hidden = !html;
  }
  function apply(d) {
    booked = new Set(d.booked);
    worked = new Set(d.worked);
    rev = d.rev;
  }
  function toggle(d) {
    if (costs(d)) { if (booked.has(d)) booked.delete(d); else booked.add(d); }
    else if (workable(d)) { if (worked.has(d)) worked.delete(d); else worked.add(d); }
    else return;
    save();
    render();
  }
  // Saves run one at a time; a change made while one is in flight is sent straight after it.
  var inFlight = false, dirty = false;
  function save() {
    if (inFlight) { dirty = true; return; }
    inFlight = true; dirty = false; mode = "saving";
    var body = JSON.stringify({ rev: rev, booked: Array.from(booked).sort(),
                                worked: Array.from(worked).sort() });
    fetch("api/days", { method: "PUT", body: body, headers: { "Content-Type": "application/json" } })
      .then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      })
      .then(function (res) {
        inFlight = false;
        if (res.status === 200) {
          rev = res.body.rev;
          if (dirty) { save(); return; }
          mode = "live"; notice("");
        } else if (res.status === 409) {
          apply(res.body); dirty = false; mode = "live";
          notice("The file was changed somewhere else, so the latest version has been loaded. " +
                 "Make your change again.");
        } else { mode = "error"; notice("Could not save: " + esc(res.body.error || res.status)); }
        render();
      })
      .catch(function () {
        inFlight = false;
        mode = "error";
        notice("Could not reach the planner server, so that change was not saved. Is " +
               "<code>holiday-planner</code> still running?");
        render();
      });
  }
  // ── Events ──
  function highlight(btn, on) {
    if (!btn) return;
    for (var i = IDX[btn.dataset.from]; i <= IDX[btn.dataset.to]; i++) cells[DAYS[i]].classList.toggle("run", on);
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest(".tab");
    if (t) { ui.tab = t.dataset.tab; saveUi(); render(); return; }
    var seg = e.target.closest("button[data-ui]");
    if (seg) { ui[seg.dataset.ui] = seg.dataset.val; saveUi(); render(); return; }
    var c = e.target.closest(".c[data-book], .c[data-work]");
    if (c) { toggle(c.dataset.date); return; }
    var b = e.target.closest("[data-rm], [data-pick]");
    if (b) toggle(b.dataset.rm || b.dataset.pick);
  });
  document.addEventListener("change", function (e) {
    var el = e.target.closest("[data-ui]");
    if (!el) return;
    ui[el.dataset.ui] = el.type === "checkbox" ? el.checked : el.value;
    saveUi();
    render();
  });
  document.querySelector(".tabs").addEventListener("keydown", function (e) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    var tabs = Array.from(document.querySelectorAll(".tab"));
    var i = tabs.findIndex(function (t) { return t.dataset.tab === ui.tab; });
    i = (i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
    ui.tab = tabs[i].dataset.tab; saveUi(); render(); tabs[i].focus();
  });
  var best = document.getElementById("best");
  ["mouseover", "focusin"].forEach(function (ev) {
    best.addEventListener(ev, function (e) { highlight(e.target.closest(".pick"), true); });
  });
  ["mouseout", "focusout"].forEach(function (ev) {
    best.addEventListener(ev, function (e) { highlight(e.target.closest(".pick"), false); });
  });

  render();
})();
</script>"""


DATA_FILE = None                       # set by --data; tests point this at a scratch file


def data_path():
    return DATA_FILE or os.path.join(PROJECT, "Notes", f"{Y0}-{Y1}",
                                     f"days-off-{Y0}-{str(Y1)[2:]}.json")


def load_data():
    """The days-off file: booked days (taken once past) and worked days, plus a revision."""
    try:
        raw = json.load(io.open(data_path(), encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    return {"year": f"{Y0}-{Y1}", "rev": int(raw.get("rev", 0)),
            "booked": sorted(raw.get("booked", [])), "worked": sorted(raw.get("worked", []))}


def check_days(days, field):
    if not isinstance(days, list):
        raise ValueError(f"{field} must be a list")
    out = set()
    for x in days:
        try:
            day = d(x)
        except (TypeError, ValueError):
            raise ValueError(f"{field}: {x!r} is not a YYYY-MM-DD date")
        if not START <= day <= END:
            raise ValueError(f"{field}: {x} is outside the planning year")
        out.add(day.isoformat())
    return sorted(out)


def save_data(booked, worked, rev):
    data = {"year": f"{Y0}-{Y1}", "rev": rev,
            "updated": dt.datetime.now().isoformat(timespec="seconds"),
            "booked": booked, "worked": worked}
    path = data_path()
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)          # atomic, so Dropbox never syncs a half-written file
    return data


def render(data=None):
    data = data or load_data()
    months, y, m = [], Y0, 9
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    grids = "\n".join(month_html(a, b) for a, b in months)
    pools = json.dumps({str(y): {"habils": v["habils"], "habilsTaken": v.get("habils_taken", 0),
                                 "recovery": v["recovery"],
                                 "recoveryTaken": v.get("recovery_taken", 0)}
                        for y, v in sorted(ENTITLEMENT.items())})
    py = f"{Y0}-{Y1}"
    body = BODY.replace("__PYL__", f"{Y0}–{str(Y1)[2:]}").replace("__GRIDS__", grids)
    current = json.dumps({k: data[k] for k in ("rev", "booked", "worked")}).replace("</", "<\\/")
    recovery = json.dumps([{"date": x.isoformat(), "name": RED[x]}
                           for x in sorted(RED) if x.weekday() >= 5 and START <= x <= END])
    script = (SCRIPT.replace("__POOLS__", pools).replace("__PY__", py).replace("__DATA__", current)
              .replace("__RECOVERY__", recovery))
    fonts = ("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600"
             "&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Holiday Planner</title>
<link rel="stylesheet" href="{fonts}">
<style>{CSS}</style>
</head>
<body>
{body}
{script}
</body>
</html>
'''


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves the planner and its days-off file. Bound to localhost only."""

    lock = threading.Lock()

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self.send(200, render(), "text/html; charset=utf-8")   # rebuilt each load
        elif path == "/api/days":
            self.send(200, json.dumps(load_data()))
        else:
            self.send(404, json.dumps({"error": "not found"}))

    def do_PUT(self):
        if self.path.split("?")[0] != "/api/days":
            return self.send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            booked = check_days(body.get("booked", []), "booked")
            worked = check_days(body.get("worked", []), "worked")
        except (ValueError, json.JSONDecodeError) as e:
            return self.send(400, json.dumps({"error": str(e)}))
        with self.lock:
            current = load_data()
            if body.get("rev") != current["rev"]:
                return self.send(409, json.dumps(current))      # changed elsewhere
            saved = save_data(booked, worked, current["rev"] + 1)
        self.send(200, json.dumps(saved))

    def log_message(self, fmt, *args):
        pass


def serve(port, open_browser):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"holiday planner at {url}")
    print(f"saving to {data_path()}")
    print("Ctrl+C to stop")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="Mark's holiday planner. Runs locally and saves to the days-off file.")
    parser.add_argument("command", nargs="?", choices=["serve"], help=argparse.SUPPRESS)
    parser.add_argument("-p", "--port", type=int, default=8737, help="port (default 8737)")
    parser.add_argument("--no-open", action="store_true", help="don't open a browser")
    parser.add_argument("--data", help=f"days-off file to use (default: {data_path()}). "
                                       "Point tests at a scratch copy, never the real file.")
    args = parser.parse_args()
    global DATA_FILE
    DATA_FILE = args.data
    serve(args.port, not args.no_open)


if __name__ == "__main__":
    main()
