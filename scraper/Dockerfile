# Base Python slim (Debian 12 bookworm, soportado por Playwright 1.49;
# trixie NO lo es) + SOLO Chromium (app.py no usa firefox/webkit).
# Imagen final ~1.3 GB vs ~2.5 GB de mcr.microsoft.com/playwright/python
# que empaqueta los 3 navegadores.
FROM python:3.11-slim-bookworm
WORKDIR /app
# procps trae pkill: app.py mata chromes zombies tras cada scrape local.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium
COPY app.py ./
EXPOSE 5000
CMD ["python", "app.py"]
