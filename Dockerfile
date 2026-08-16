FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir '.[postgres]'
COPY AGENTS.md ./

RUN useradd --create-home --uid 10001 devpilot && mkdir -p /data/repositories && chown -R devpilot:devpilot /data /app
USER devpilot

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
