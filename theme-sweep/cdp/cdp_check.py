"""Phone-width checks for a theme review, over the DevTools protocol.

Usage: python3 -I cdp_check.py <base-url> <theme-slug> [width] [path ...]

Two rules this script exists to enforce, both learned the hard way on 2026-11-11:

1. `mobile: false`. With `mobile: true` Chromium applies a virtual viewport that
   grows until the content fits, so a page with a horizontal overflow reports
   scrollWidth == innerWidth and nothing past the right edge. The test then
   passes in exactly the case it exists to catch. The width read-back below is
   what detects it, because the grown viewport is never the width requested.

2. Assert the active theme on every page measured, not once per run. On a shared
   install another session can switch the theme between two halves of one script,
   and the symptom is a selector finding nothing - which reads like a finding and
   is not one.

Overflow is measured on every URL. Where NAV and TOGGLE below match the theme,
the open mobile menu also gets a keyboard pass: Tab to the toggle, Enter, then Tab
until focus leaves the nav, comparing what took focus against the links in the DOM
rather than stopping after a fixed number of presses. Results are printed per URL; anything whose theme or
viewport does not check out is reported as ABORT and recorded nowhere.
"""
import json
import subprocess
import sys
import time
import urllib.request

import websocket

BASE = sys.argv[1].rstrip("/")
THEME = sys.argv[2]
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 390
PATHS = [a for a in sys.argv[4:] if not a.startswith("--")] or ["/"]
# Selector pairs (nav container, opener) for the keyboard pass, tried in order on
# each page; the first pair whose both halves exist is used, so one script covers a
# classic theme and a block theme. Add a theme's own pair at the front when it uses
# neither. Pass --no-keyboard to skip the pass entirely.
SELECTOR_SETS = [
    ("#site-navigation", ".menu-toggle"),
    (".wp-block-navigation__responsive-container",
     ".wp-block-navigation__responsive-container-open"),
    ("nav", "button[aria-expanded]"),
]
KEYBOARD = "--no-keyboard" not in sys.argv
PORT = 9371


def start():
    proc = subprocess.Popen(
        ["chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
         "--ignore-certificate-errors", "--hide-scrollbars",
         "--remote-debugging-port=%d" % PORT, "--window-size=%d,844" % WIDTH,
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            pages = [t for t in json.load(urllib.request.urlopen(
                "http://127.0.0.1:%d/json" % PORT)) if t.get("type") == "page"]
            if pages:
                return proc, pages[0]["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.3)
    proc.kill()
    sys.exit("no debugger target")


proc, ws_url = start()
ws = websocket.create_connection(ws_url, timeout=60)
n = [0]


def send(method, params=None):
    n[0] += 1
    ws.send(json.dumps({"id": n[0], "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == n[0]:
            return r


def ev(expr):
    return send("Runtime.evaluate", {"expression": expr, "returnByValue": True})["result"]["result"].get("value")


def key(name, code, vk, text=None):
    p = {"type": "keyDown", "key": name, "code": code,
         "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    if text:
        p["text"] = text
    send("Input.dispatchKeyEvent", p)
    send("Input.dispatchKeyEvent", {"type": "keyUp", "key": name, "code": code,
                                    "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
    time.sleep(0.09)


send("Page.enable")
for path in PATHS:
    send("Page.navigate", {"url": BASE + path})
    time.sleep(3.5)
    send("Emulation.setDeviceMetricsOverride",
         {"width": WIDTH, "height": 844, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(1)
    theme = ev("var l=document.querySelector('link[href*=\"/themes/\"]');"
               "l ? l.href.split('/themes/')[1].split('/')[0] : 'none'")
    inner = ev("window.innerWidth")
    if theme != THEME or inner != WIDTH:
        print("%s ABORT theme=%s innerWidth=%s" % (path, theme, inner))
        continue
    print("%s theme=%s innerWidth=%s scrollWidth=%s past_edge=%s" % (
        path, theme, inner, ev("document.documentElement.scrollWidth"),
        ev("JSON.stringify([].slice.call(document.querySelectorAll('body *'))"
           ".filter(function(e){var r=e.getBoundingClientRect();"
           "return r.width>0&&r.right>window.innerWidth+1;}).slice(0,6)"
           ".map(function(e){return e.tagName+'.'+(e.className||'').toString().split(' ')[0];}))")))

    if not KEYBOARD:
        continue
    NAV = TOGGLE = None
    for nav_sel, open_sel in SELECTOR_SETS:
        if ev("!!document.querySelector('%s') && !!document.querySelector('%s')" % (nav_sel, open_sel)):
            NAV, TOGGLE = nav_sel, open_sel
            break
    if not NAV:
        print("  keyboard: no nav and opener pair matched on this page")
        continue
    print("  keyboard: using %s / %s" % (NAV, TOGGLE))
    # No small cap here: a theme with a long header puts many stops before the
    # opener, and giving up early would read like an accessibility finding.
    for _ in range(60):
        key("Tab", "Tab", 9)
        if ev("document.activeElement.matches('%s')" % TOGGLE):
            break
    else:
        print("  keyboard: opener never took focus in 60 Tab presses")
        continue
    key("Enter", "Enter", 13, "\r")
    time.sleep(0.6)
    probe = ("(function(){var a=document.activeElement,nav=document.querySelector('%s');"
             "if(!a||!nav.contains(a))return JSON.stringify({out:true});"
             "var cs=getComputedStyle(a),r=a.getBoundingClientRect(),nr=nav.getBoundingClientRect();"
             "var was=a.dataset.cdpSeen==='1';a.dataset.cdpSeen='1';"
             "return JSON.stringify({text:(a.textContent||'').trim().slice(0,30),cycled:was,"
             "ok:(a.matches(':focus-visible')&&cs.outlineStyle!=='none'"
             "&&r.top>=nr.top-1&&r.bottom<=nr.bottom+1&&r.top>=0&&r.bottom<=window.innerHeight)});})()") % NAV
    seen, bad, ended = [], [], "hit the 200-element runaway guard"
    while len(seen) < 200:
        key("Tab", "Tab", 9)
        d = json.loads(ev(probe))
        if d.get("out"):
            ended = "focus left the nav"
            break
        if d.get("cycled"):
            # A focus trap in the open panel cycles rather than letting focus out.
            ended = "focus cycled back inside the panel"
            break
        seen.append(d["text"])
        if not d["ok"]:
            bad.append(d["text"])
    in_dom = json.loads(ev("JSON.stringify([].slice.call(document.querySelectorAll('%s a'))"
                           ".map(function(a){return a.textContent.trim().slice(0,30);}))" % NAV))
    key("Escape", "Escape", 27)
    time.sleep(0.4)
    missing = [x for x in in_dom if x not in seen]
    # Stops and links are counted separately: a close button is a stop, not a link,
    # so "6 of 5" would read like a defect. The exact claim is the missing list.
    print("  keyboard: %d stops covering %d of %d links (%s), never focused %s, no focus ring or out of view %s, escape returns to opener %s" % (
        len(seen), len(in_dom) - len(missing), len(in_dom), ended, json.dumps(missing),
        json.dumps(bad), ev("document.activeElement.matches('%s')" % TOGGLE)))

ws.close()
proc.kill()
