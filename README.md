# 🎬 Family Trailer Studio

Turn family photos + a story into a Hollywood-style trailer — English voiceover
narration with Hebrew on-screen captions, Ken Burns motion, music with ducking,
SFX, cast cards, and hair→bald style reveals.

This is the productized version of the "Operation Hair Transfer" pipeline: the
proven per-video scripts are now **one data-driven engine** driven by a JSON spec.

## Architecture (3 layers)

1. **Engine** (`engine/`) — ✅ built. Takes a trailer spec (JSON) → renders an MP4.
   - `scenes.py` — `SceneRenderer`: bakes each scene into 1920×1080 frames
     (`black_card`, `photo`, `cast_card`, `coming_soon`, `reveal`, `video`).
   - `tts.py` — narration backends. `SapiNarrator` (Windows) today; Piper (cloud) next.
   - `assemble.py` — `Assembler`: ffmpeg Ken Burns / xfade reveals / video overlay,
     music ducking, concat.
   - `render.py` — `build_trailer(spec)`: narration → frames → assembly.
2. **AI writer** (`ai/`) — ✅ built. Claude (`claude-opus-4-8`): family brief + labelled
   photos → a full trailer spec (story beats, EN narration, HE captions, effects).
   - `catalog.py` — enumerates the real music/sfx so the model can only pick files that exist.
   - `writer.py` — `TrailerWriter.write(brief)`: prompts Claude, parses JSON, then
     validates against the engine + assets and does a repair round-trip on any error.
   - `validate.py` — `validate_spec()`: the contract check (scene types, required fields,
     images/music/sfx exist) — gates a spec before render and drives repair.
   - Needs `ANTHROPIC_API_KEY` (or `ant auth login`) to call the model live. The full
     machinery is proven offline in `samples/test_ai_offline.py` (stub client, no key).
3. **Web app** (`web/` + `server/`) — ✅ built. Browser UI, private + local.
   - `server/app.py` — FastAPI: create project, upload photos, AI-write, background
     render (thread + status polling), serve the MP4. Photos live per-project; music/sfx
     come from a shared media LIBRARY (env `FTS_LIBRARY`).
   - `web/index.html` — self-contained RTL Hebrew SPA: upload+label photos → describe
     the family → AI writes the script → one click renders → inline player + download.

### Run the web app

```bash
python -m server.app            # then open http://127.0.0.1:8000
```

Set `ANTHROPIC_API_KEY` for the AI "write script" step. The render path also works
from a spec directly (`POST /api/project/{id}/spec`) with no key.

## Run the engine

```bash
python -m engine.render samples/demo_spec.json          # render a spec
python samples/test_ai_offline.py                        # AI-writer machinery, no API key
python -m ai.writer samples/brief_example.json           # AI writer LIVE (needs ANTHROPIC_API_KEY)
```

Output lands in `samples/_work*/`. See `samples/demo_spec.json` for the spec shape —
every scene is a plain dict, so the AI writer just emits this JSON.

## Spec quick reference

- Top level: `assets_root`, `music_dir`, `sfx_dir`, `resolution`, `fps`, `narration`, `scenes[]`.
- Each scene: `id`, `type`, timing (`duration`, `music`, `music_offset`, `sfx`,
  `zoom_in`, `narration`, `narration_delay`).
- `reveal` scenes carry `before`/`after` sub-scenes + `transition`
  (`fadewhite` for reframed pairs, `dissolve` for pixel-aligned pairs).

## Notes

- Narration voiceover is English; on-screen captions are the Hebrew translation.
- The vo work dir must stay ASCII (PowerShell 5.1 mangles Hebrew paths).
- Cloud rendering will swap `SapiNarrator` → Piper and bundle the fonts; nothing
  else in the engine changes.
