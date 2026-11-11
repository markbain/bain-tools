"""SUPERSEDED by cdp_check.py. Kept only as a worked example of the raw CDP calls.
Two defects: it sets mobile: true in setDeviceMetricsOverride, which lets the virtual
viewport grow until the content fits and so hides a horizontal overflow, and it never
asserts which theme the page it measures is running. Read cdp_check.py first.
"""
"""Screenshot a URL at a forced viewport, optionally after running JS."""
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

URL, OUT, WIDTH, HEIGHT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
JS = sys.argv[5] if len(sys.argv) > 5 else None

proc = subprocess.Popen(
    ["chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
     "--ignore-certificate-errors", "--hide-scrollbars",
     "--remote-debugging-port=9333", "--window-size=%d,%d" % (WIDTH, HEIGHT),
     "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

ws_url = None
for _ in range(50):
    try:
        tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
        for t in tabs:
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
msg_id = [0]


def send(method, params=None):
    msg_id[0] += 1
    ws.send(json.dumps({"id": msg_id[0], "method": method, "params": params or {}}))
    while True:
        res = json.loads(ws.recv())
        if res.get("id") == msg_id[0]:
            return res


send("Page.enable")
send("Emulation.setDeviceMetricsOverride",
     {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": True})
send("Page.navigate", {"url": URL})
time.sleep(4)
print("innerWidth:", send("Runtime.evaluate", {"expression": "window.innerWidth"})["result"]["result"]["value"])
print("scrollWidth:", send("Runtime.evaluate", {"expression": "document.documentElement.scrollWidth"})["result"]["result"]["value"])
if JS:
    out = send("Runtime.evaluate", {"expression": JS})
    print("js:", json.dumps(out.get("result", {}).get("result", {})))
    time.sleep(1.5)
shot = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
with open(OUT, "wb") as fh:
    fh.write(base64.b64decode(shot["result"]["data"]))
print("written", OUT)
ws.close()
proc.kill()
