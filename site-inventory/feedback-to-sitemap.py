#!/usr/bin/env python3
"""Turn a client-annotated site inventory into a draft IA source document.

The inventory goes to the client as a spreadsheet (site-inventory.py --format
csv). They mark each row with a decision and notes. Exported back to CSV, this
script writes the ## Structure document the claude.ai Information Architecture
project charts, in the format its instructions set out:

    - Name `/path/` {template} [status]
      An indented line with no bullet is a note on the page above.

Every row is converted the same way, so the run can be repeated whenever the
sheet changes. Restructuring (moving, grouping, new pages) is left to the IA
project: this script only records what the client decided about each page.

Decisions map to the four statuses the IA format allows:

    keep     -> [keep]
    rewrite  -> [keep]  + "Rewrite: <notes>"
    delete   -> [drop]  + the notes + "Redirect: to decide"
    rethink  -> [keep]  + "Open question: <notes>"

Anything else is kept and flagged as an open question, never guessed. A note
that contradicts its row's decision ("DELETE" on a rewrite row) is flagged as
a conflict for the next pass.

Usage:
    feedback-to-sitemap.py feedback.csv --title "Client" \\
        --decision-col Action --note-col "Notes" [--note-col "More notes"] \\
        -o sitemap.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys

STATUS = {"keep": "keep", "rewrite": "keep", "delete": "drop", "drop": "drop",
          "rethink": "keep"}
DELETE_WORDS = re.compile(r"\b(delete|remove|drop)\b", re.I)
KEEP_WORDS = re.compile(r"\bkeep\b", re.I)


def clean(text) -> str:
    """One line, trimmed, with spreadsheet artefacts removed."""
    text = " ".join((text or "").split())
    return "" if text in ('""', "''") else text


def label_of(col: str) -> str:
    """'Hazel's Notes' -> 'Hazel', so each note says whose it is."""
    return re.sub(r"('s)?\s*notes?$", "", col, flags=re.I).strip() or col


def conflict(decision: str, notes: list[str]) -> str:
    """A note that says the opposite of the decision, for the next pass."""
    said = " ".join(notes)
    says_delete, says_keep = DELETE_WORDS.search(said), KEEP_WORDS.search(said)
    if decision in ("keep", "rewrite") and says_delete and not says_keep:
        return "the decision is %s but a note says delete" % decision
    if decision in ("delete", "drop") and says_keep and not says_delete:
        return "the decision is delete but a note says keep"
    return ""


def page_lines(row, decision, notes, depth):
    title = clean(row.get("title")) or row["path"]
    bits = ["%s- %s `%s`" % ("  " * depth, title, row["path"])]
    template, kind = clean(row.get("template")), clean(row.get("kind"))
    if template:
        bits.append("{%s}" % template)
    elif kind and kind != "page":
        bits.append("{%s}" % kind)
    bits.append("[%s]" % STATUS.get(decision, "keep"))

    lines = [" ".join(bits)]
    pad = "  " * depth + "  "
    said = "; ".join(text for _, text in notes)
    labelled = "; ".join("%s: %s" % n for n in notes)

    if decision not in STATUS:
        lines.append(pad + "Open question: no decision recorded%s%s" % (
            " (%s)" % decision if decision else "",
            ". %s" % labelled if notes else ""))
    elif decision == "rewrite":
        lines.append(pad + "Rewrite" + (". %s" % labelled if notes else ""))
    elif decision == "rethink":
        lines.append(pad + "Open question" + (". %s" % labelled if notes else ""))
    elif decision in ("delete", "drop"):
        if notes:
            lines.append(pad + labelled)
        lines.append(pad + "Redirect: to decide")
    elif notes:
        lines.append(pad + labelled)

    why = conflict(decision, [said])
    if why:
        lines.append(pad + "Conflict: %s. Settle in the next pass." % why)
    return lines


def ordered(rows):
    """Parents before children, each level in path order, Home first."""
    by_path = {r["path"]: r for r in rows}
    children, roots = {}, []
    for r in sorted(rows, key=lambda r: r["path"]):
        parent = clean(r.get("tree_parent"))
        if parent and parent in by_path and parent != r["path"]:
            children.setdefault(parent, []).append(r)
        else:
            roots.append(r)
    roots.sort(key=lambda r: (r["path"] != "/", r["path"]))
    out = []

    def walk(r, depth):
        out.append((r, depth))
        for c in children.get(r["path"], []):
            walk(c, depth + 1)

    for r in roots:
        walk(r, 0)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", help="the annotated inventory, exported as CSV")
    ap.add_argument("--title", default="", help="the document's # title")
    ap.add_argument("--decision-col", default="Action",
                    help="column holding keep/rewrite/delete/rethink (default: Action)")
    ap.add_argument("--note-col", action="append", default=[],
                    help="column of notes to carry onto the page; repeatable")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if clean(r.get("path"))]
    if not rows:
        sys.exit("feedback-to-sitemap: no rows with a path in %s" % args.csv)
    missing = [c for c in [args.decision_col, *args.note_col] if c not in rows[0]]
    if missing:
        sys.exit("feedback-to-sitemap: no column named %s" % ", ".join(map(repr, missing)))

    out = (["# %s" % args.title, ""] if args.title else []) + ["## Structure", ""]
    counts, conflicts = {}, 0
    for row, depth in ordered(rows):
        decision = clean(row.get(args.decision_col)).lower()
        notes = []
        for col in args.note_col:
            text = clean(row.get(col))
            # A note that only repeats the decision adds nothing.
            if text and text.lower().rstrip(".!") not in (decision, "keep", "delete", "rewrite"):
                notes.append((label_of(col), text))
        lines = page_lines(row, decision, notes, depth)
        conflicts += any("Conflict:" in l for l in lines)
        key = decision or "(none)"
        counts[key] = counts.get(key, 0) + 1
        out += lines
    text = "\n".join(out) + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    print("feedback-to-sitemap: %d pages (%s); %d conflicts flagged" % (
        len(rows), ", ".join("%s %d" % kv for kv in sorted(counts.items())), conflicts),
        file=sys.stderr)


if __name__ == "__main__":
    main()
