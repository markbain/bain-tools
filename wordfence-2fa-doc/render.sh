#!/usr/bin/env bash
#
# Render the Wordfence 2FA walkthrough for one client.
#
# Substitutes the client name and login URL into the master template, writes
# the result to the client's Dropbox Dev Ops folder, and renders the branded
# PDF with brand-doc.
#
# Usage:
#   ./render.sh "Client Name" "https://example.com/wp-admin/"

set -euo pipefail

CLIENT="${1:?usage: render.sh \"Client Name\" \"https://example.com/wp-admin/\"}"
LOGIN_URL="${2:?usage: render.sh \"Client Name\" \"https://example.com/wp-admin/\"}"

CONTENT_DIR="/media/data/Dropbox/Work/Content/Wordfence 2FA"
TEMPLATE="${CONTENT_DIR}/wordfence-2fa-walkthrough-template.md"
MANIFEST="${CONTENT_DIR}/images/manifest.json"
DEST_DIR="/media/data/Dropbox/Work/clients/${CLIENT}/Dev Ops"
DEST_MD="${DEST_DIR}/wordfence-2fa-walkthrough.md"
DEST_PDF="${DEST_DIR}/wordfence-2fa-walkthrough.pdf"

[[ -f "$TEMPLATE" ]] || { echo "template not found: $TEMPLATE" >&2; exit 1; }
[[ -d "$DEST_DIR" ]] || { echo "no Dev Ops folder for '${CLIENT}': $DEST_DIR" >&2; exit 1; }

read_manifest() {
  python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$MANIFEST" "$1"
}
WF_VERSION="$(read_manifest wordfence)"
WP_VERSION="$(read_manifest wordpress)"
CAPTURE_DATE="$(read_manifest captured)"

# brand-doc resolves image paths relative to the Markdown file, so the images
# have to sit beside the rendered copy, not back in the Content folder.
mkdir -p "${DEST_DIR}/images"
cp "${CONTENT_DIR}/images/"*.png "${DEST_DIR}/images/"

python3 - "$TEMPLATE" "$DEST_MD" "$CLIENT" "$LOGIN_URL" "$WF_VERSION" "$WP_VERSION" "$CAPTURE_DATE" <<'PY'
import sys
src, dest, client, url, wf, wp, date = sys.argv[1:8]
text = open(src).read()
for token, value in (
    ("{{CLIENT_NAME}}", client),
    ("{{LOGIN_URL}}", url),
    ("{{WF_VERSION}}", wf),
    ("{{WP_VERSION}}", wp),
    ("{{CAPTURE_DATE}}", date),
):
    text = text.replace(token, value)
left = [t for t in ("{{CLIENT_NAME}}", "{{LOGIN_URL}}") if t in text]
if left:
    sys.exit(f"placeholders left unsubstituted: {left}")
open(dest, "w").write(text)
print(f"wrote {dest}")
PY

brand-doc "$DEST_MD" "$DEST_PDF"
echo "PDF: ${DEST_PDF}"
