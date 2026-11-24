#!/usr/bin/env bash
#
# Render the Wordfence 2FA walkthrough as a branded PDF.
#
# The walkthrough is generic: it names no client and no site, so one PDF goes
# to everybody. The only substitutions are the Wordfence and WordPress versions
# and the capture date, taken from the manifest the capture run writes, so the
# footer always matches the screenshots rather than being typed by hand.
#
# Usage:
#   ./render.sh [output.pdf]

set -euo pipefail

CONTENT_DIR="/media/data/Dropbox/Work/Content/Wordfence 2FA"
TEMPLATE="${CONTENT_DIR}/wordfence-2fa-walkthrough-template.md"
MANIFEST="${CONTENT_DIR}/images/manifest.json"
BUILD_MD="${CONTENT_DIR}/wordfence-2fa-walkthrough.md"
OUT_PDF="${1:-${CONTENT_DIR}/wordfence-2fa-walkthrough.pdf}"

[[ -f "$TEMPLATE" ]] || { echo "template not found: $TEMPLATE" >&2; exit 1; }
[[ -f "$MANIFEST" ]] || { echo "manifest not found, re-run shoot.sh: $MANIFEST" >&2; exit 1; }

python3 - "$TEMPLATE" "$BUILD_MD" "$MANIFEST" <<'PY'
import json, sys, datetime
src, dest, manifest_path = sys.argv[1:4]
m = json.load(open(manifest_path))

# The date appears in prose written to a person, so day-before-month, not ISO.
captured = datetime.date.fromisoformat(m["captured"]).strftime("%-d %B %Y")

text = open(src).read()
for token, value in (
    ("{{WF_VERSION}}", m["wordfence"]),
    ("{{WP_VERSION}}", m["wordpress"]),
    ("{{CAPTURE_DATE}}", captured),
):
    text = text.replace(token, value)

import re
left = re.findall(r"\{\{[A-Z_]+\}\}", text)
if left:
    sys.exit(f"placeholders left unsubstituted: {sorted(set(left))}")
open(dest, "w").write(text)
print(f"wrote {dest}")
PY

brand-doc "$BUILD_MD" "$OUT_PDF"
echo "PDF: ${OUT_PDF}"
