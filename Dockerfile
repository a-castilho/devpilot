FROM node:22-bookworm-slim AS codex-cli

# Install Codex in an isolated build stage. The npm registry occasionally resets
# long-lived connections on slow/mobile links, so use both npm-level retries and
# a retry around the complete install. The runtime image does not need npm.
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_FACTOR=2 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_FETCH_TIMEOUT=300000

RUN set -eux; \
    npm config set registry https://registry.npmjs.org/; \
    installed=0; \
    for attempt in 1 2 3 4; do \
        echo "Codex npm install attempt ${attempt}/4"; \
        if npm install -g --no-audit --no-fund @openai/codex; then \
            installed=1; \
            break; \
        fi; \
        npm cache clean --force || true; \
        sleep $((attempt * 10)); \
    done; \
    [ "$installed" = "1" ]; \
    codex --version

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# The worker executes Git and Codex inside this image. Keep the runtime lean:
# Debian installs only the small native tools needed at runtime. espeak-ng is
# used on demand as the no-API fallback when Chromium/Brave exposes Web Speech
# but cannot actually synthesize audio on Linux.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git espeak-ng \
    && git --version \
    && espeak-ng --version \
    && rm -rf /var/lib/apt/lists/*

COPY --from=codex-cli /usr/local/bin/node /usr/local/bin/node
COPY --from=codex-cli /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -sf /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
    && chmod +x /usr/local/lib/node_modules/@openai/codex/bin/codex.js \
    && node --version \
    && codex --version

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
