# -*- coding: utf-8 -*-
"""Render a Hebrew test scene on the LIVE cloud app and download the mp4,
to verify RTL (Hebrew) renders correctly. Usage: python cloud_rtl_test.py <out.mp4>"""
import json
import os
import sys
import time
import urllib.request
from http.cookiejar import CookieJar

U = "https://family-trailer-studio-production.up.railway.app"
PW = os.environ.get("FTS_PASSWORD", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "cloud_rtl.mp4"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def post(path, obj=None):
    data = json.dumps(obj).encode() if obj is not None else b""
    req = urllib.request.Request(U + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req, timeout=60).read().decode())


def get(path):
    return json.loads(opener.open(U + path, timeout=60).read().decode())


post("/api/login", {"password": PW})
print("login ok")
pid = post("/api/project")["project_id"]
spec = {"title": "RTL", "scenes": [{
    "id": "t", "type": "black_card", "duration": 3.0, "music": "01_Opening_Theme.mp3",
    "zoom_in": True, "narration": "In a family of legends.",
    "lines": [
        {"t": "IN A FAMILY OF LEGENDS...", "f": "IMP", "s": 96, "y": 460, "c": "WHITE", "tr": 8, "st": 2},
        {"t": "במשפחה של אגדות...", "f": "HE", "s": 72, "y": 600, "c": "GOLD", "rtl": True, "st": 2},
    ]}]}
post(f"/api/project/{pid}/spec", spec)
post(f"/api/project/{pid}/render")
for _ in range(40):
    time.sleep(3)
    st = get(f"/api/project/{pid}/status")
    if st["state"] != "rendering":
        print("render:", st["state"]); break
# download the mp4
urllib.request.urlopen  # noqa
data = opener.open(U + f"/api/project/{pid}/video", timeout=120).read()
with open(OUT, "wb") as f:
    f.write(data)
print("saved", OUT, len(data), "bytes")
