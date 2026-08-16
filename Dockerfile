FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates git nodejs npm \
    && npm install --global @openai/codex \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir '.[postgres]'
COPY AGENTS.md ./
COPY scripts/devpilot-git-askpass.sh /usr/local/bin/devpilot-git-askpass
RUN chmod 755 /usr/local/bin/devpilot-git-askpass

RUN useradd --create-home --uid 10001 devpilot && mkdir -p /data/repositories && chown -R devpilot:devpilot /data /app
USER devpilot

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
