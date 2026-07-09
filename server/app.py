# -*- coding: utf-8 -*-
"""Family Trailer Studio — web backend (Layer 3).

Ties the engine + AI writer to a browser UI: create a project, upload photos,
let the AI write the trailer, render it in the background, download the MP4.

Run:  python -m server.app        (then open http://127.0.0.1:8000)

Photos live in each project's dir; music/sfx come from a shared media LIBRARY
(env FTS_LIBRARY; defaults to the Operation Hair Transfer folder which ships the
audio). Everything is local + private — no accounts, no cloud, for the family.
"""
import json
import os
import threading
import uuid

import hashlib
import io
import socket

from fastapi import FastAPI, UploadFile, File, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")
WEB = BASE + "/web"
PROJECTS = os.environ.get("FTS_PROJECTS", BASE + "/_projects").replace("\\", "/")
os.makedirs(PROJECTS, exist_ok=True)

LIBRARY = os.environ.get("FTS_LIBRARY", BASE + "/library").replace("\\", "/")
MUSIC_DIR = LIBRARY + "/03_Music"
SFX_DIR = LIBRARY + "/04_Sound FX"

# Narration voices (Piper neural, cloud). Each id -> a .onnx in FTS_VOICES_DIR.
# /api/voices returns only the ones actually present, so this degrades gracefully
# (e.g. locally, where SAPI is used and no /app/voices exists -> picker hidden).
VOICES_DIR = os.environ.get("FTS_VOICES_DIR", "/app/voices").replace("\\", "/")
VOICES = [
    {"id": "us_female",  "label": "👩 אישה · אמריקאי",       "file": "en_US-lessac-medium.onnx"},
    {"id": "us_female2", "label": "👩 אישה · אמריקאי (חם)",  "file": "en_US-amy-medium.onnx"},
    {"id": "us_male",    "label": "🧔 גבר · אמריקאי",         "file": "en_US-ryan-high.onnx"},
    {"id": "uk_male",    "label": "🧔 גבר · בריטי",           "file": "en_GB-alan-medium.onnx"},
    {"id": "uk_female",  "label": "👩 אישה · בריטי",          "file": "en_GB-jenny_dioco-medium.onnx"},
]


def _voice_model(vid):
    v = next((v for v in VOICES if v["id"] == vid), None)
    if not v:
        return None
    mp = f"{VOICES_DIR}/{v['file']}"
    return mp if os.path.isfile(mp) else None

app = FastAPI(title="Family Trailer Studio")
JOBS = {}  # project_id -> {state, message}
PORT = int(os.environ.get("PORT", 8000))


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ---- family password gate (protects the app when exposed to the internet) ----
AUTH_PW = os.environ.get("FTS_PASSWORD", "").strip()


def _auth_token():
    return hashlib.sha256((AUTH_PW + "|fts-v1").encode()).hexdigest()


LOGIN_HTML = """<!doctype html><html lang=he dir=rtl><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>כניסה</title>
<style>body{margin:0;background:#0d0d10;color:#f0f0f0;font-family:'Segoe UI',Arial,sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center}
.box{background:#17171c;border:1px solid #2b2b34;border-radius:16px;padding:32px;width:320px;text-align:center}
h1{font-size:22px;margin:0 0 6px}p{color:#9a9aa6;margin:0 0 18px;font-size:14px}
input{width:100%;box-sizing:border-box;background:#1f1f26;color:#f0f0f0;border:1px solid #2b2b34;
border-radius:10px;padding:12px;font-size:16px;margin-bottom:12px}
button{width:100%;background:#d8b23c;color:#111;border:0;border-radius:10px;padding:12px;font-size:16px;font-weight:700;cursor:pointer}
.err{color:#f08080;font-size:14px;min-height:18px}</style></head><body>
<div class=box><h1>🎬 מפעל הטריילרים</h1><p>הזינו את סיסמת המשפחה</p>
<input id=pw type=password placeholder="סיסמה" autofocus>
<button onclick=go()>כניסה</button><div class=err id=err></div></div>
<script>async function go(){const pw=document.getElementById('pw').value;
const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
if(r.ok){location.reload()}else{document.getElementById('err').textContent='סיסמה שגויה'}}
document.getElementById('pw').addEventListener('keydown',e=>{if(e.key==='Enter')go()});</script>
</body></html>"""


@app.middleware("http")
async def _auth(request: Request, call_next):
    if not AUTH_PW or request.url.path in ("/api/login", "/api/diag"):
        return await call_next(request)
    if request.cookies.get("fts_auth") == _auth_token():
        return await call_next(request)
    if request.url.path == "/":
        return HTMLResponse(LOGIN_HTML)
    return JSONResponse({"detail": "unauthorized"}, status_code=401)


@app.post("/api/login")
def login(body: dict = Body(...)):
    if AUTH_PW and (body.get("password", "") == AUTH_PW):
        r = JSONResponse({"ok": True})
        r.set_cookie("fts_auth", _auth_token(), max_age=60 * 60 * 24 * 30,
                     httponly=True, samesite="lax")
        return r
    raise HTTPException(401, "wrong password")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".aac")


def _pdir(pid):
    d = f"{PROJECTS}/{pid}"
    if not os.path.isdir(d):
        raise HTTPException(404, "project not found")
    return d


def _scene_summary(scenes):
    out = []
    for s in scenes:
        t = s.get("type")
        if t in ("black_card", "logo"):
            txt = " / ".join(l["t"] for l in s.get("lines", []))
        elif t == "photo":
            txt = s.get("caption", "")
        elif t == "cast_card":
            txt = f'{s.get("name", "")} — {s.get("role", "")}'
        elif t == "reveal":
            b, a = s.get("before", {}), s.get("after", {})
            txt = f'{b.get("name") or b.get("caption") or "?"} → {a.get("name") or a.get("caption") or "?"}'
        elif t == "coming_soon":
            txt = s.get("subtitle", "COMING SOON")
        elif t == "video":
            txt = s.get("overlay_caption", "🎬 video")
        else:
            txt = ""
        out.append({"id": s.get("id"), "type": t, "narration": s.get("narration", ""), "text": txt})
    return out


# ---- pages -----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    with open(WEB + "/index.html", "r", encoding="utf-8") as fh:
        return fh.read()


@app.get("/api/info")
def info():
    return {"lan_url": f"http://{_lan_ip()}:{PORT}"}


@app.get("/api/diag")
def diag():
    res = {"in": "אבג"}
    try:
        import importlib.metadata as md
        res["ver"] = md.version("python-bidi")
    except Exception as e:
        res["ver"] = f"err:{e}"
    try:
        from bidi.algorithm import get_display as g1
        res["algorithm"] = g1("אבג")
    except Exception as e:
        res["algorithm"] = f"err:{e}"
    try:
        from bidi import get_display as g2
        res["toplevel"] = g2("אבג")
    except Exception as e:
        res["toplevel"] = f"err:{e}"
    try:
        from engine import scenes
        res["scenes_uses"] = scenes.get_display("אבג")      # the EXACT function the render uses
    except Exception as e:
        res["scenes_uses"] = f"err:{e}"
    return res


@app.get("/api/qr")
def qr():
    import qrcode
    img = qrcode.make(f"http://{_lan_ip()}:{PORT}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# ---- project lifecycle -----------------------------------------------------
@app.post("/api/project")
def create_project():
    pid = uuid.uuid4().hex[:12]
    os.makedirs(f"{PROJECTS}/{pid}/uploads", exist_ok=True)
    return {"project_id": pid, "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/project/{pid}/photos")
async def upload_photos(pid: str, files: list[UploadFile] = File(...)):
    d = _pdir(pid)
    saved = []
    for f in files:
        name = os.path.basename(f.filename).replace("/", "_")
        dest = f"{d}/uploads/{name}"
        with open(dest, "wb") as out:
            out.write(await f.read())
        kind = "video" if name.lower().endswith(VIDEO_EXT) else "image"
        saved.append({"file": f"uploads/{name}", "label": "", "kind": kind})
    return {"photos": saved}


@app.get("/api/project/{pid}/photo")
def get_photo(pid: str, path: str):
    d = _pdir(pid)
    full = os.path.normpath(f"{d}/{path}").replace("\\", "/")
    if not full.startswith(f"{d}/uploads/") or not os.path.isfile(full):
        raise HTTPException(404, "photo not found")
    return FileResponse(full)


@app.get("/api/music")
def music_list():
    from ai.catalog import build_catalog
    cat = build_catalog(LIBRARY, MUSIC_DIR, SFX_DIR)
    return {"music": cat["music"]}


@app.get("/api/music/file")
def music_file(name: str):
    safe = os.path.basename(name)
    full = f"{MUSIC_DIR}/{safe}"
    if not os.path.isfile(full):
        raise HTTPException(404, "track not found")
    return FileResponse(full, media_type="audio/mpeg")


@app.get("/api/voices")
def voices_list():
    """Only voices whose model file is present (cloud). Empty locally -> UI hides picker."""
    return {"voices": [{"id": v["id"], "label": v["label"]}
                       for v in VOICES if _voice_model(v["id"])]}


@app.get("/api/voice/preview")
def voice_preview(id: str):
    mp = _voice_model(id)
    if not mp:
        raise HTTPException(404, "voice not available")
    import tempfile
    import subprocess
    sample = "Every family has a story worth telling."
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run([os.environ.get("FTS_PIPER_CMD", "piper"), "--model", mp,
                        "--output_file", wav], input=sample, text=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        data = open(wav, "rb").read()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"preview failed: {e}")
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
    return Response(data, media_type="audio/wav")


@app.get("/api/project/{pid}/music")
def project_music(pid: str):
    d = _pdir(pid)
    from ai.catalog import build_catalog
    lib = build_catalog(LIBRARY, MUSIC_DIR, SFX_DIR)["music"]
    updir = f"{d}/uploads"
    up = sorted(f"uploads/{f}" for f in os.listdir(updir)
                if f.lower().endswith(AUDIO_EXT)) if os.path.isdir(updir) else []
    return {"music": lib + up}


@app.post("/api/project/{pid}/music")
async def upload_music(pid: str, files: list[UploadFile] = File(...)):
    d = _pdir(pid)
    added = []
    for f in files:
        name = os.path.basename(f.filename).replace("/", "_")
        if not name.lower().endswith(AUDIO_EXT):
            continue
        with open(f"{d}/uploads/{name}", "wb") as out:
            out.write(await f.read())
        added.append(f"uploads/{name}")
    return {"added": added}


@app.post("/api/project/{pid}/write")
def write_spec(pid: str, body: dict = Body(...)):
    d = _pdir(pid)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY is not set — set it (or run `ant auth login`) "
                                 "to let the AI write the story.")
    from ai.writer import TrailerWriter
    items = body.get("photos", [])
    images = [p for p in items if p.get("kind") != "video"]
    videos = [{"file": p["file"], "label": p.get("label", "")} for p in items if p.get("kind") == "video"]
    brief = {
        "title": body.get("title", "Family Trailer"),
        "assets_root": d,
        "music_dir": MUSIC_DIR,
        "sfx_dir": SFX_DIR,
        "story": body.get("story", ""),
        "photos": images,
        "videos": videos,
        "notes": body.get("notes", ""),
        "work_dir": f"{d}/_work",
        "output": f"{d}/trailer.mp4",
    }
    try:
        writer = TrailerWriter(d, music_dir=MUSIC_DIR, sfx_dir=SFX_DIR)
        spec = writer.write(brief)
    except Exception as e:
        raise HTTPException(500, f"AI writer failed: {e}")
    with open(f"{d}/spec.json", "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
    return {"title": spec.get("title"), "spec": spec, "count": len(spec["scenes"])}


@app.post("/api/project/{pid}/spec")
def set_spec(pid: str, spec: dict = Body(...)):
    """Store a spec directly (manual mode / testing without the AI)."""
    d = _pdir(pid)
    spec.setdefault("assets_root", d)
    spec.setdefault("music_dir", MUSIC_DIR)
    spec.setdefault("sfx_dir", SFX_DIR)
    spec["work_dir"] = f"{d}/_work"
    spec["output"] = f"{d}/trailer.mp4"
    with open(f"{d}/spec.json", "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
    return {"title": spec.get("title"), "spec": spec, "count": len(spec["scenes"])}


# ---- live translation (Hebrew caption -> English narration) ----------------
@app.post("/api/translate")
def translate(body: dict = Body(...)):
    text = (body.get("text") or "").strip()
    if not text:
        return {"narration": ""}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY is not set")
    from anthropic import Anthropic
    sys = ("You turn a Hebrew on-screen caption from a family movie-trailer into ONE short, punchy "
           "ENGLISH voiceover line in cinematic trailer-narration style. Natural and evocative, not a "
           "stiff word-for-word translation. Output ONLY the English line — no quotes, no notes, no preamble.")
    try:
        client = Anthropic()
        r = client.messages.create(model="claude-opus-4-8", max_tokens=120,
                                   system=[{"type": "text", "text": sys}],
                                   messages=[{"role": "user", "content": text}])
        out = "".join(b.text for b in r.content if b.type == "text").strip().strip('"')
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"translate failed: {e}")
    return {"narration": out}


# ---- render ----------------------------------------------------------------
def _render(pid, spec_path):
    from engine.render import build_trailer
    JOBS[pid] = {"state": "rendering", "message": "מרנדר את הטריילר..."}
    try:
        with open(spec_path, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
        # resolve the picked voice (Piper/cloud) into the narrator options
        if os.environ.get("FTS_TTS_BACKEND") == "piper":
            mp = _voice_model(spec.get("voice"))
            if mp:
                spec.setdefault("narration", {}).setdefault("options", {})["model"] = mp
        build_trailer(spec, verbose=True)
        JOBS[pid] = {"state": "done", "message": "הטריילר מוכן!"}
    except Exception as e:  # noqa: BLE001
        JOBS[pid] = {"state": "error", "message": str(e)}


@app.post("/api/project/{pid}/render")
def start_render(pid: str):
    d = _pdir(pid)
    spec_path = f"{d}/spec.json"
    if not os.path.isfile(spec_path):
        raise HTTPException(400, "no spec yet — write or set one first")
    if JOBS.get(pid, {}).get("state") == "rendering":
        return {"state": "rendering"}
    threading.Thread(target=_render, args=(pid, spec_path), daemon=True).start()
    return {"state": "started"}


@app.get("/api/project/{pid}/status")
def status(pid: str):
    _pdir(pid)
    return JOBS.get(pid, {"state": "idle", "message": ""})


@app.get("/api/project/{pid}/video")
def video(pid: str):
    d = _pdir(pid)
    mp4 = f"{d}/trailer.mp4"
    if not os.path.isfile(mp4):
        raise HTTPException(404, "trailer not rendered yet")
    return FileResponse(mp4, media_type="video/mp4", filename="family_trailer.mp4")


if __name__ == "__main__":
    import uvicorn
    import threading
    import webbrowser
    url = f"http://127.0.0.1:{PORT}"
    if os.environ.get("FTS_OPEN_BROWSER", "1") == "1":           # local only; off in the cloud
        threading.Timer(1.6, lambda: webbrowser.open(url)).start()
    print("=" * 48)
    print("  Family Trailer Studio")
    print("  On this PC:               ", url)
    print("  On your phone (same WiFi):", f"http://{_lan_ip()}:{PORT}")
    print("=" * 48)
    uvicorn.run(app, host="0.0.0.0", port=PORT)   # 0.0.0.0 = reachable from phones on the LAN
