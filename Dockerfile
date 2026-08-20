FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# The worker executes Git and Codex inside this same image. Keep both tools
# in the runtime image so queued development/analysis tasks do not fail with
# "command not found" as soon as the worker picks them up.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git nodejs npm \
    && npm install -g @openai/codex \
    && git --version \
    && codex --version \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir '.[postgres]'
COPY app ./app
COPY README.md AGENTS.md ./

RUN useradd --create-home --uid 10001 devpilot \
    && mkdir -p /data/repositories \
    && chown -R devpilot:devpilot /data /app
USER devpilot

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
