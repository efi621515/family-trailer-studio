# Family Trailer Studio — cloud image (Railway / any Docker host)
FROM python:3.11-slim

# ffmpeg (video), wget (fetch the voice model)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Piper neural voice (English narration) — offline, free
RUN mkdir -p /app/voices && \
    wget -qO /app/voices/en_US-lessac-medium.onnx \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" && \
    wget -qO /app/voices/en_US-lessac-medium.onnx.json \
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

COPY . .

ENV FTS_FONTS_DIR=/app/fonts \
    FTS_TTS_BACKEND=piper \
    FTS_PIPER_MODEL=/app/voices/en_US-lessac-medium.onnx \
    FTS_LIBRARY=/app/library \
    FTS_PROJECTS=/app/data/_projects \
    FTS_OPEN_BROWSER=0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "-m", "server.app"]
