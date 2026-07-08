# Deploying Family Trailer Studio to Railway

The app is cloud-ready: `Dockerfile` builds it, Piper handles the voice on Linux,
fonts are bundled, and the server reads `PORT` from the environment.

## What you set on Railway (environment variables)
- `ANTHROPIC_API_KEY` — your Anthropic key (for the AI writer + translation)
- `FTS_PASSWORD` — the family password (login gate)
- `PORT` — set automatically by Railway (don't add it yourself)

Baked into the image already: `FTS_TTS_BACKEND=piper`, `FTS_FONTS_DIR`, `FTS_LIBRARY`,
`FTS_PROJECTS=/app/data/_projects`, `FTS_OPEN_BROWSER=0`.

## Persistence (so uploads/renders survive restarts)
Add a **Volume** in Railway mounted at **`/app/data`** (the projects dir lives there).

---

## Path A — Railway CLI (no GitHub needed)
```bash
npm i -g @railway/cli
railway login
railway init                 # create a new project
railway up                   # builds the Dockerfile and deploys
# then in the dashboard: add the two variables + a volume at /app/data
railway domain               # get your public URL
```

## Path B — GitHub + Railway dashboard
1. Push this folder to a new GitHub repo.
2. Railway → **New Project → Deploy from GitHub repo** → pick the repo (it detects the Dockerfile).
3. **Variables** tab → add `ANTHROPIC_API_KEY` and `FTS_PASSWORD`.
4. **Volumes** → add a volume mounted at `/app/data`.
5. **Settings → Networking → Generate Domain** → your permanent public URL.

---

## After deploy
- Open the URL → family password page → in.
- The first render downloads the depth model only if 3D is enabled (3D is a later phase).
- Voice is Piper (English narration); Hebrew captions render from the bundled fonts.

## Notes / limits of this first cloud version
- No GPU → 3D (when added) renders on CPU (slower). Fine for occasional use.
- One small instance handles a family's occasional use; heavy concurrent use needs a bigger plan.
