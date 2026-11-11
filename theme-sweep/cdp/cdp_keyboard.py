"""SUPERSEDED by cdp_check.py. Kept only as a worked example of the raw CDP calls.
Two defects: it sets mobile: true in setDeviceMetricsOverride, which lets the virtual
viewport grow until the content fits and so hides a horizontal overflow, and it never
asserts which theme the page it measures is running. Read cdp_check.py first.
"""
"""Keyboard pass at a forced phone viewport, using real key events."""
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

URL = sys.argv[1]
OUT = sys.argv[2]
WIDTH, HEIGHT = 390, 844

proc = subprocess.Popen(
    ["chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
     "--ignore-certificate-errors", "--hide-scrollbars",
     "--remote-debugging-port=9334", "--window-size=%d,%d" % (WIDTH, HEIGHT),
     "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

ws_url = None
for _ in range(50):
    try:
        for t in json.load(urllib.request.urlopen("http://127.0.0.1:9334/json")):
            if t.get("type") == "page":
                ws_url = t["webSocketDebuggerUrl"]
        if ws_url:
            break
    except Exception:
        pass
    time.sleep(0.2)
if not ws_url:
    proc.kill()
    sys.exit("no target")

ws = websocket.create_connection(ws_url, timeout=30)
n = [0]


def send(method, params=None):
    n[0] += 1
    ws.send(json.dumps({"id": n[0], "method": method, "params": params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == n[0]:
            return r


def ev(expr):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r["result"]["result"].get("value")


def key(name, code, vk, text=None):
    for typ in ("keyDown", "keyUp"):
        p = {"type": typ, "key": name, "code": code, "windowsVirtualKeyCode": vk,
             "nativeVirtualKeyCode": vk}
        if text and typ == "keyDown":
            p["type"] = "keyDown"
            p["text"] = text
        send("Input.dispatchKeyEvent", p)
    time.sleep(0.12)


send("Page.enable")
send("Emulation.setDeviceMetricsOverride",
     {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": True})
send("Page.navigate", {"url": URL})
time.sleep(4)

PROBE = """(function(){
 var a=document.activeElement;
 if(!a) return 'none';
 var cs=getComputedStyle(a), r=a.getBoundingClientRect();
 var nav=document.getElementById('site-navigation');
 var nr=nav?nav.getBoundingClientRect():null;
 return JSON.stringify({
  tag:a.tagName, cls:(a.className||'').toString().slice(0,40),
  text:(a.textContent||'').trim().slice(0,30),
  outline:cs.outlineStyle+' '+cs.outlineWidth+' '+cs.outlineColor,
  ring: a.matches(':focus-visible'),
  rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
  inViewport: r.top>=0 && r.bottom<=window.innerHeight && r.height>0,
  inNav: nr? (r.top>=nr.top-1 && r.bottom<=nr.bottom+1) : null,
  navRect: nr?[Math.round(nr.y),Math.round(nr.height)]:null,
  expanded: (document.querySelector('.menu-toggle')||{}).getAttribute ? document.querySelector('.menu-toggle').getAttribute('aria-expanded') : null
 });})()"""

log = []
print("== tab sequence from load ==")
for i in range(6):
    key("Tab", "Tab", 9)
    s = ev(PROBE)
    print(i + 1, s)
    log.append(s)
    if '"cls":"menu-toggle' in (s or ""):
        print(">> toggle reached at stop", i + 1)
        break

print("== Enter on current element ==")
key("Enter", "Enter", 13, "\r")
time.sleep(0.6)
print("after enter:", ev(PROBE))

print("== tab through the open menu ==")
for i in range(16):
    key("Tab", "Tab", 9)
    s = ev(PROBE)
    print("m%d" % (i + 1), s)
    log.append(s)

print("== Escape ==")
key("Escape", "Escape", 27)
time.sleep(0.4)
print("after escape:", ev(PROBE))

shot = send("Page.captureScreenshot", {"format": "png"})
with open(OUT, "wb") as fh:
    fh.write(base64.b64decode(shot["result"]["data"]))
print("shot", OUT)
ws.close()
proc.kill()
