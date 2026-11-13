#!/usr/bin/env python3
"""Drive one administrator through Wordfence 2FA enrolment and capture the screens.

Called by shoot.sh, which builds the throwaway site first. Every frame is an
element screenshot, cropped to the panel the walkthrough step refers to, with a
CSS outline injected on the control named in that step. Nothing is drawn at
fixed pixel coordinates, so the highlights survive a Wordfence UI change.

TOTP is computed here rather than read from a phone: the enrolment screen shows
the shared secret, which is all a TOTP code needs.
"""

import argparse
import base64
import hashlib
import hmac
import json
import struct
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# --- TOTP -------------------------------------------------------------------


def totp(secret_b32, when=None, digits=6, step=30):
    """RFC 6238 TOTP, SHA-1, the variant every authenticator app implements."""
    secret = secret_b32.strip().replace(" ", "").upper()
    secret += "=" * (-len(secret) % 8)
    key = base64.b32decode(secret)
    counter = int((when if when is not None else time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def fresh_code(secret: str) -> str:
    """Return a code with enough of its window left to survive the round trip."""
    remaining = 30 - (time.time() % 30)
    if remaining < 5:
        time.sleep(remaining + 0.5)
    return totp(secret)


# --- capture helpers --------------------------------------------------------

HIDE_NOISE = """
#wf-onboarding-banner, #wpadminbar, .notice, .wfls-admin-notice,
#wpfooter, #screen-meta, #screen-meta-links, .update-nag,
.wfls-time-ip-info { display: none !important; }
"""

HIGHLIGHT = """
.shoot-highlight {
  outline: 3px solid #d64000 !important;
  outline-offset: 3px !important;
  border-radius: 3px !important;
}
"""

REDACT = """
.shoot-redact {
  color: transparent !important;
  text-shadow: 0 0 9px rgba(0,0,0,0.85) !important;
}
"""


class Shoot:
    def __init__(self, page, out: Path):
        self.page = page
        self.out = out
        self.n = 0
        self.frames = []

    def style(self):
        self.page.add_style_tag(content=HIDE_NOISE + HIGHLIGHT + REDACT)

    def mark(self, selector: str, cls: str = "shoot-highlight"):
        self.page.eval_on_selector_all(
            selector, "(els, c) => els.forEach(e => e.classList.add(c))", cls
        )

    def unmark(self, cls: str = "shoot-highlight"):
        self.page.evaluate(
            "(c) => document.querySelectorAll('.' + c).forEach(e => e.classList.remove(c))", cls
        )

    def frame(self, name: str, selector: str, note: str):
        """Crop to `selector` and write the next numbered PNG."""
        self.n += 1
        path = self.out / f"{self.n:02d}-{name}.png"
        self.page.wait_for_timeout(400)
        self.page.locator(selector).first.screenshot(path=str(path))
        self.frames.append({"file": path.name, "note": note})
        print(f"    [{self.n:02d}] {path.name} — {note}")


# --- the run ----------------------------------------------------------------


def login(page, url, user, password):
    page.goto(f"{url}/wp-login.php", wait_until="networkidle")
    page.fill("#user_login", user)
    page.fill("#user_pass", password)
    page.click("#wp-submit")
    page.wait_for_load_state("networkidle")


def open_ls(page, url, tab="manage"):
    page.goto(f"{url}/wp-admin/admin.php?page=WFLS", wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.click(f"#wfls-tab-{tab} a")
    page.wait_for_timeout(1800)


def find_secret(page):
    """Read the shared secret off the enrolment panel.

    Wordfence 9.x prints it in a readonly text input beside the QR code, which
    is the same string the QR encodes.
    """
    el = page.locator("#wfls-qr-code-text").first
    el.wait_for(state="visible", timeout=20000)
    secret = (el.input_value() or "").strip()
    if not secret:
        raise RuntimeError("the enrolment panel rendered but the secret field was empty")
    return secret


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 1100},
            device_scale_factor=2,
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        login(page, args.url, args.user, args.password)

        shoot = Shoot(page, out)

        # 1. Where the page lives. No dashboard banner appeared for the
        #    unenrolled administrator on this site, but that is not evidence
        #    one never appears: a site whose only administrator has no 2FA is
        #    the case Wordfence suppresses the requirement for. Untested with a
        #    second enrolled admin. Either way the walkthrough needs to say
        #    where to go. Captured from the page itself, submenu already open.
        open_ls(page, args.url, tab="manage")
        page.add_style_tag(content=HIDE_NOISE + HIGHLIGHT + REDACT)
        shoot.mark("#adminmenu a:has-text('Login Security')")
        shoot.frame("find-login-security", "#adminmenu",
                    "Where to go: Wordfence, then Login Security")
        shoot.unmark()

        # 2. The enrolment panel: QR code and the typed-in alternative.
        open_ls(page, args.url, tab="manage")
        shoot.style()
        secret = find_secret(page)
        print(f"    secret read from panel ({len(secret)} chars)")
        shoot.mark("#wfls-qr-code, #wfls-qr-code-text")
        shoot.mark("ul.wfls-recovery-codes li", cls="shoot-redact")
        shoot.frame("scan-or-type", "#wfls-tab-content-manage, #manage",
                    "Scan the QR code, or type the key into the app instead")
        shoot.unmark()
        shoot.unmark("shoot-redact")

        # 3. Recovery codes. Shown on the same screen in 9.x, before activation.
        shoot.mark("ul.wfls-recovery-codes li", cls="shoot-redact")
        shoot.mark("ul.wfls-recovery-codes")
        shoot.frame("recovery-codes", "ul.wfls-recovery-codes",
                    "Recovery codes, blurred here. The client saves their own")
        shoot.unmark()
        shoot.unmark("shoot-redact")

        # 4. The step people miss: a code typed in, Activate not yet pressed.
        # Type the code rather than fill it: Wordfence enables the Activate
        # link on keystrokes, so a programmatic fill leaves it disabled.
        page.click("#wfls-activate-field")
        for ch in fresh_code(secret):
            page.keyboard.press(ch)
            page.wait_for_timeout(60)
        page.wait_for_function(
            "() => { const a = document.querySelector('#wfls-activate');"
            " return a && !a.classList.contains('wfls-disabled'); }",
            timeout=10000,
        )
        shoot.mark("#wfls-activate-field, #wfls-activate")
        shoot.mark("ul.wfls-recovery-codes li", cls="shoot-redact")
        shoot.frame("enter-code-and-activate", "#wfls-tab-content-manage, #manage",
                    "Code entered and Activate pressed. Scanning alone does nothing")
        shoot.unmark()
        shoot.unmark("shoot-redact")

        # 5. Activate. If the recovery codes were never downloaded, Wordfence
        #    interrupts with a reminder, which is worth a frame of its own.
        page.click("#wfls-activate")
        page.wait_for_timeout(3500)
        modal = page.locator(".wfls-modal:visible").first
        if modal.count():
            shoot.frame("save-codes-reminder", ".wfls-modal:visible",
                        "Wordfence asks again for the recovery codes before it finishes")
            for label in ("Skip", "Continue", "OK", "Close"):
                btn = page.locator(f".wfls-modal:visible a:has-text('{label}'), "
                                   f".wfls-modal:visible button:has-text('{label}')").first
                if btn.count():
                    btn.click()
                    break
            page.wait_for_timeout(3000)

        # 6. The confirmation that enrolment actually took.
        open_ls(page, args.url, tab="manage")
        shoot.style()
        shoot.frame("activated", "#wfls-tab-content-manage, #manage",
                    "Two-factor authentication now active for this user")

        # 7. The next sign-in, now asking for a code.
        page.goto(f"{args.url}/wp-admin/", wait_until="networkidle")
        logout = page.locator("#wp-admin-bar-logout a").first
        if logout.count():
            page.goto(logout.get_attribute("href"), wait_until="networkidle")
        if page.locator("text=log out").count():
            page.click("text=log out")
            page.wait_for_load_state("networkidle")
        page.goto(f"{args.url}/wp-login.php", wait_until="networkidle")
        page.fill("#user_login", args.user)
        page.fill("#user_pass", args.password)
        page.click("#wp-submit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        page.add_style_tag(content=HIGHLIGHT)
        shoot.mark("#wfls-token, input[name='wfls-token']")
        shoot.frame("login-code-prompt", "#loginform, form[name='loginform']",
                    "From now on: password, then a code from the app")
        shoot.unmark()

        manifest = {
            "wordfence": args.wf_version,
            "wordpress": args.wp_version,
            "captured": time.strftime("%Y-%m-%d"),
            "frames": shoot.frames,
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"    manifest written to {out / 'manifest.json'}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wf-version", default="unknown")
    ap.add_argument("--wp-version", default="unknown")
    args = ap.parse_args()
    try:
        run(args)
    except Exception as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
