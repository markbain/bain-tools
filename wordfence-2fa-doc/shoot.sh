#!/usr/bin/env bash
#
# Re-shoot the Wordfence 2FA walkthrough screenshots.
#
# Builds a throwaway DDEV WordPress site with neutral, invented branding,
# installs the current Wordfence free release, drives one administrator
# through 2FA enrolment with Playwright/Chromium, writes cropped PNGs, and
# tears the site down again.
#
# Nothing here touches a client site. The site title, user and email are
# invented so the screenshots can go in a studio template reused across
# clients.
#
# Usage:
#   ./shoot.sh [output-dir]
#
# KEEP_SITE=1 leaves the DDEV site up for debugging.

set -euo pipefail

SITE_NAME="wf-2fa-shots"
SITE_DIR="/media/data/dev/ddev/${SITE_NAME}"
SITE_TITLE="Northgate Supplies"
ADMIN_USER="a.morgan"
ADMIN_PASS="shoot-2fa-walkthrough"
ADMIN_EMAIL="a.morgan@northgate-supplies.test"
SITE_URL="https://${SITE_NAME}.ddev.site"

OUT_DIR="${1:-/media/data/Dropbox/Work/Content/Wordfence 2FA/images}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

keep_site="${KEEP_SITE:-0}"

teardown() {
  if [[ "$keep_site" == "1" ]]; then
    echo "KEEP_SITE=1, leaving ${SITE_DIR} in place."
    return
  fi
  echo "--> Tearing down ${SITE_NAME}"
  if [[ -d "$SITE_DIR" ]]; then
    (cd "$SITE_DIR" && ddev delete -Oy >/dev/null 2>&1) || true
    rm -rf "$SITE_DIR"
  fi
}
trap teardown EXIT

if [[ -d "$SITE_DIR" ]]; then
  echo "--> Removing a previous ${SITE_NAME}"
  (cd "$SITE_DIR" && ddev delete -Oy >/dev/null 2>&1) || true
  rm -rf "$SITE_DIR"
fi

echo "--> Creating ${SITE_DIR}"
mkdir -p "$SITE_DIR"
cd "$SITE_DIR"

ddev config --project-name="$SITE_NAME" --project-type=wordpress --docroot=. >/dev/null
ddev start -y >/dev/null

echo "--> Installing WordPress"
ddev wp core download >/dev/null
ddev wp config create --dbname=db --dbuser=db --dbpass=db --dbhost=db --force >/dev/null
ddev wp core install \
  --url="$SITE_URL" \
  --title="$SITE_TITLE" \
  --admin_user="$ADMIN_USER" \
  --admin_password="$ADMIN_PASS" \
  --admin_email="$ADMIN_EMAIL" \
  --skip-email >/dev/null

echo "--> Removing bundled noise"
ddev wp plugin delete akismet hello >/dev/null 2>&1 || true
ddev wp post delete 1 2 3 --force >/dev/null 2>&1 || true

echo "--> Installing Wordfence"
ddev wp plugin install wordfence --activate >/dev/null
WF_VERSION="$(ddev wp plugin get wordfence --field=version | tr -d '\r')"
WP_VERSION="$(ddev wp core version | tr -d '\r')"
echo "    Wordfence ${WF_VERSION} on WordPress ${WP_VERSION}"

echo "--> Enabling 2FA site-wide and requiring it for administrators"
# Clicking the toggle in the UI does not persist reliably, and the admin side is
# not part of the walkthrough anyway: this just puts the site in the state a
# client's site is already in.
ddev wp eval '
$c = \WordfenceLS\Controller_Settings::shared();
$c->set("enable-2fa", 1);
$c->set("require-2fa.administrator", 1);
$c->set("2fa-user-grace-period", 10);
$c->set("require-2fa-grace-period-enabled", 1);
' >/dev/null

echo "--> Capturing"
mkdir -p "$OUT_DIR"
python3 "${HERE}/capture.py" \
  --url "$SITE_URL" \
  --user "$ADMIN_USER" \
  --password "$ADMIN_PASS" \
  --out "$OUT_DIR" \
  --wf-version "$WF_VERSION" \
  --wp-version "$WP_VERSION"

echo "--> Done. PNGs in ${OUT_DIR}"
