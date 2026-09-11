FROM node:22-bookworm-slim AS codex-cli

# Keep Codex on the known-good release and pin Gemini CLI for deterministic builds.
ARG CODEX_VERSION=0.148.0
ARG GEMINI_VERSION=0.59.0
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_FACTOR=2 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_FETCH_TIMEOUT=300000

RUN set -eux; \
    npm config set registry https://registry.npmjs.org/; \
    installed=0; \
    for attempt in 1 2 3 4; do \
        echo "AI CLI install attempt ${attempt}/4"; \
        if npm install -g --no-audit --no-fund \
            "@openai/codex@${CODEX_VERSION}" \
            "@google/gemini-cli@${GEMINI_VERSION}"; then \
            installed=1; \
            break; \
        fi; \
        npm cache clean --force || true; \
        sleep $((attempt * 10)); \
    done; \
    [ "$installed" = "1" ]; \
    codex --version | grep -F "${CODEX_VERSION}"; \
    gemini --version | grep -F "${GEMINI_VERSION}"

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=8

WORKDIR /app

RUN set -eux; \
    installed=0; \
    for attempt in 1 2 3 4; do \
        echo "APT dependency install attempt ${attempt}/4"; \
        rm -rf /var/lib/apt/lists/*; \
        if apt-get update -o Acquire::Retries=3 \
            && apt-get install -y --no-install-recommends ca-certificates git espeak-ng; then \
            installed=1; \
            break; \
        fi; \
        sleep $((attempt * 15)); \
    done; \
    [ "$installed" = "1" ]; \
    git --version; \
    espeak-ng --version; \
    rm -rf /var/lib/apt/lists/*

COPY --from=codex-cli /usr/local/bin/node /usr/local/bin/node
COPY --from=codex-cli /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
COPY --from=codex-cli /usr/local/lib/node_modules/@google /usr/local/lib/node_modules/@google
RUN ln -sf /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex \
    && ln -sf /usr/local/lib/node_modules/@google/gemini-cli/bundle/gemini.js /usr/local/bin/gemini \
    && chmod +x /usr/local/lib/node_modules/@openai/codex/bin/codex.js \
    && chmod +x /usr/local/lib/node_modules/@google/gemini-cli/bundle/gemini.js \
    && node --version \
    && codex --version \
    && gemini --version

COPY pyproject.toml README.md AGENTS.md ./
COPY app ./app

RUN set -eux; \
    installed=0; \
    for attempt in 1 2 3 4; do \
        echo "Python dependency install attempt ${attempt}/4"; \
        if pip install --no-cache-dir '.[postgres,rag]'; then \
            installed=1; \
            break; \
        fi; \
        sleep $((attempt * 15)); \
    done; \
    [ "$installed" = "1" ]

RUN useradd --create-home --uid 10001 devpilot \
    && mkdir -p /data/repositories \
    && chown -R devpilot:devpilot /data /app
USER devpilot

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]