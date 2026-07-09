# Family Trailer Studio — cloud image (Railway / any Docker host)
FROM python:3.11-slim

# ffmpeg (video), wget (fetch the voice model)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Piper neural voices (English narration) — offline, free. One .onnx + .onnx.json
# per voice; the app exposes them as a picker. Base path on HuggingFace piper-voices.
RUN mkdir -p /app/voices && cd /app/voices && \
    base="https://huggingface.co/rhasspy/piper-voices/resolve/main" && \
    for v in \
      en/en_US/lessac/medium/en_US-lessac-medium \
      en/en_US/amy/medium/en_US-amy-medium \
      en/en_US/ryan/high/en_US-ryan-high \
      en/en_GB/alan/medium/en_GB-alan-medium \
      en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium ; do \
        n=$(basename $v) && \
        wget -qO $n.onnx "$base/$v.onnx" && \
        wget -qO $n.onnx.json "$base/$v.onnx.json" ; \
    done

# 3D depth photos: CPU-only torch + transformers, then pre-cache the depth model
# into the image so the first 3D render doesn't stall on a ~100MB download.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.2" "transformers>=4.45" && \
    python -c "from transformers import pipeline; pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf')"

COPY . .

ENV FTS_FONTS_DIR=/app/fonts \
    FTS_TTS_BACKEND=piper \
    FTS_PIPER_MODEL=/app/voices/en_US-lessac-medium.onnx \
    FTS_LIBRARY=/app/library \
    FTS_PROJECTS=/app/data/_projects \
    FTS_OPEN_BROWSER=0 \
    FTS_FFMPEG_PRESET=veryfast \
    FTS_FFMPEG_CRF=23 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "-m", "server.app"]
