# ---- Audiocall — Twilio + Google ADK voice agent (FastAPI, Python 3.13) ----
# Dependencies are managed with uv against the committed uv.lock for reproducible
# builds. Two-step install keeps the dependency layer cached across code changes.
FROM python:3.13-slim

# uv binary from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the Google service account JSON into the image at the path the app expects.
RUN mkdir -p /home/ubuntu/audiocall
COPY google_service_account.json /home/ubuntu/audiocall/google_service_account.json
ENV GOOGLE_APPLICATION_CREDENTIALS="/home/ubuntu/audiocall/google_service_account.json"

# 1) Install only third-party deps first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Add the app and install the project itself (README is referenced by pyproject).
COPY README.md ./
COPY audiocall ./audiocall
RUN uv sync --frozen --no-dev

# Put the venv on PATH so `uvicorn` resolves without `uv run`.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# WebSocket-capable server. Single process — Gemini Live sessions are per-connection.
CMD ["uvicorn", "audiocall.main:app", "--host", "0.0.0.0", "--port", "8000"]
