# wordfence-2fa-doc

The Wordfence 2FA walkthrough that goes to clients, and the tooling that keeps
its screenshots current.

Two scripts:

| Script | What it does |
|---|---|
| `shoot.sh` | Builds a throwaway WordPress site, enrols one user in 2FA, captures the screens, tears the site down |
| `render.sh` | Fills in the captured versions and date, and renders the branded PDF |

The master template and the captured PNGs live outside this repo, in
`Work/Content/Wordfence 2FA/` in Dropbox, alongside the other client-facing
master templates.

## Re-shooting the screenshots

Wordfence ships releases often and redraws this screen from time to time. When
the screens no longer match what clients see:

```bash
./shoot.sh
```

That builds a DDEV site with invented branding ("Northgate Supplies", user
`a.morgan`), installs the current Wordfence free release, drives enrolment with
Playwright and Chromium, writes numbered PNGs plus a `manifest.json` recording
the Wordfence and WordPress versions and the capture date, and deletes the site
again. `KEEP_SITE=1 ./shoot.sh` leaves the site up for debugging.

Nothing in the run touches a client site, and no client name appears in any
frame — the same PNGs go to every client.

The frames are element screenshots cropped to the panel each step refers to,
with a CSS outline injected on the control that step names. Nothing is drawn at
fixed coordinates, so a Wordfence layout change moves the highlight with it
rather than stranding it.

TOTP codes are computed in `capture.py` from the secret the enrolment screen
prints, so no phone is involved. The implementation is checked against the
RFC 6238 SHA-1 test vectors.

## Rendering the PDF

```bash
./render.sh
```

The walkthrough names no client and no site, so one PDF goes to everybody. It
is written next to the template in Dropbox, as
`wordfence-2fa-walkthrough.pdf`, and sending it to a client is a matter of
attaching it.

The only substitutions are the Wordfence and WordPress versions and the capture
date, read from `images/manifest.json`, so the footer always matches the
screenshots. Re-run it after every `shoot.sh`.

## Known gaps

The walkthrough opens by saying where the menu item is, rather than by showing
a dashboard prompt. No prompt appeared for the unenrolled administrator during
capture, but that run cannot settle it: the site had a single administrator
with no 2FA, which is the case Wordfence suppresses the requirement for. Worth
re-testing with a second, enrolled admin before treating "there is no prompt"
as fact.

## What the doc does not cover

Enrolment only, from the client's side. Role enforcement, grace periods, the
`has_admin_with_2fa_active()` suppression behaviour and lockout recovery are
deliberately out of scope — that is studio knowledge, and it is not written
down anywhere yet.

## Requirements

DDEV, WP-CLI through DDEV, Python 3 with Playwright and its Chromium build, and
`brand-doc` on PATH.
