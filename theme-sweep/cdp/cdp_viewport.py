"""SUPERSEDED by cdp_check.py - use that instead.

Kept as a readable worked example of the raw calls. What it lacks: it does
not assert the active theme, so on a shared install a theme switch between
two halves of a run is invisible, and it has no keyboard pass.

Render a URL at a forced layout viewport and report horizontal overflow.

Uses Emulation.setDeviceMetricsOverride with mobile=False. With mobile=True
Chromium applies a virtual viewport that shrinks to fit the content, so
window.innerWidth comes back wider than the width asked for and every
measurement taken from it is wrong. The script asserts the viewport it got
before reporting anything.
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

URL, OUT, WIDTH, HEIGHT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
PORT = int(sys.argv[5]) if len(sys.argv) > 5 else 9360

proc = subprocess.Popen(
    ["chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
     "--ignore-certificate-errors", "--hide-scrollbars",
     "--remote-debugging-port=%d" % PORT, "--window-size=1200,900", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

ws_url = None
for _ in range(80):
    try:
        for t in json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % PORT)):
            if t.get("type") == "page":
                ws_url = t["webSocketDebuggerUrl"]
                break
        if ws_url:
            break
    except Exception:
        pass
    time.sleep(0.2)
if not ws_url:
    proc.kill()
    sys.exit("no debugger target")

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
    return send("Runtime.evaluate", {"expression": expr, "returnByValue": True})["result"]["result"].get("value")


send("Page.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)
send("Emulation.setDeviceMetricsOverride",
     {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": False})
time.sleep(2)

inner = ev("window.innerWidth")
if inner != WIDTH:
    ws.close()
    proc.kill()
    sys.exit("viewport is %s, asked for %s - measurement refused" % (inner, WIDTH))

OVERFLOW = """(function(){
 var out=[], w=window.innerWidth;
 document.querySelectorAll('body *').forEach(function(e){
  var r=e.getBoundingClientRect();
  if(r.right>w+1 || r.left<-1){
   out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,44),
             left:Math.round(r.left), right:Math.round(r.right), w:Math.round(r.width)});
  }});
 return JSON.stringify({inner:w, docScroll:document.documentElement.scrollWidth,
                        bodyScroll:document.body.scrollWidth, count:out.length, worst:out.slice(0,10)});
})()"""

print("url:", URL)
print("innerWidth:", inner)
print(ev(OVERFLOW))
shot = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
with open(OUT, "wb") as fh:
    fh.write(base64.b64decode(shot["result"]["data"]))
print("written", OUT)
ws.close()
proc.kill()
