# -*- coding: utf-8 -*-
"""Narration synthesis.

Backend abstraction so the engine is not tied to Windows SAPI. Today: the proven
SAPI backend (Windows-only). Tomorrow (cloud): a Piper backend with the same
`synth_all(items, out_dir)` contract — swap the backend, everything else stays.

IMPORTANT: out_dir must be an ASCII path. PowerShell 5.1 mangles Hebrew paths from
a UTF-8 script, so keep the vo work dir ASCII-only.
"""
import os
import subprocess
import tempfile


class SapiNarrator:
    """Windows SAPI TTS via a generated PowerShell script (English narration)."""

    def __init__(self, voice="Microsoft David Desktop", rate=-2, pitch="-15%", volume=100, **_):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def synth_all(self, items, out_dir):
        """items: list of (id, text). Writes <out_dir>/<id>.wav for each. Returns map id->path."""
        out_dir = out_dir.replace("\\", "/").rstrip("/") + "/"
        os.makedirs(out_dir, exist_ok=True)
        lines = []
        for sid, text in items:
            if not text:
                continue
            safe = text.replace("'", "''")
            lines.append("@{n='%s'; t='%s'}" % (sid, safe))
        ps = (
            "Add-Type -AssemblyName System.Speech\n"
            "$dir = '%s'\n"
            "New-Item -ItemType Directory -Force -Path $dir | Out-Null\n"
            "$lines = @(\n  %s\n)\n"
            "foreach ($l in $lines) {\n"
            "  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            "  $s.SelectVoice('%s')\n"
            "  $s.Rate = %d\n  $s.Volume = %d\n"
            "  $path = Join-Path $dir ($l.n + '.wav')\n"
            "  $s.SetOutputToWaveFile($path)\n"
            "  $ssml = \"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><prosody pitch='%s'>\" + $l.t + \"</prosody></speak>\"\n"
            "  $s.SpeakSsml($ssml)\n  $s.Dispose()\n}\n"
            "Write-Output 'VO DONE'\n"
        ) % (out_dir, ",\n  ".join(lines), self.voice, self.rate, self.volume, self.pitch)

        fd, path = tempfile.mkstemp(suffix=".ps1", text=True)
        with os.fdopen(fd, "w", encoding="ascii", errors="replace") as fh:
            fh.write(ps)
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", path], check=True)
        finally:
            os.remove(path)
        return {sid: out_dir + sid + ".wav" for sid, text in items if text}


class PiperNarrator:
    """Piper neural TTS (offline, free, Linux/cloud). English narration.

    Uses the `piper` CLI with a downloaded voice model (.onnx). Same
    synth_all(items, out_dir) contract as SapiNarrator.
    """

    def __init__(self, model=None, voice_cmd="piper", **_):
        self.model = model or os.environ.get("FTS_PIPER_MODEL")
        self.voice_cmd = voice_cmd

    def synth_all(self, items, out_dir):
        out_dir = out_dir.replace("\\", "/").rstrip("/") + "/"
        os.makedirs(out_dir, exist_ok=True)
        result = {}
        for sid, text in items:
            if not text:
                continue
            wav = out_dir + sid + ".wav"
            subprocess.run([self.voice_cmd, "--model", self.model, "--output_file", wav],
                           input=text, text=True, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result[sid] = wav
        return result


def get_narrator(backend=None, **kw):
    backend = backend or os.environ.get("FTS_TTS_BACKEND") or "sapi"
    if backend == "sapi":
        return SapiNarrator(**kw)
    if backend == "piper":
        return PiperNarrator(**kw)
    raise ValueError(f"unknown TTS backend: {backend}")
