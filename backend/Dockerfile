# syntax=docker/dockerfile:1
# GEIS backend — imagen de la API FastAPI.
# Construcción: docker build -t geis-backend ./backend
# La API espera PostgreSQL+PostGIS accesible vía DATABASE_URL.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias de sistema necesarias para compilar/instalar requirements:
#  - libpq-dev / gcc: psycopg2-binary (rueda precompilada, pero por si acaso)
#  - libgeos / proj: shapely y pyproj traen ruedas propias; se dejan los
#    paquetes base por si el runtime necesita las libs compartidas.
#  - curl: necesario para el healthcheck del servicio api
#    (curl -f http://localhost:8000/health) definido en docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

# Migraciones se aplican fuera (job de infra o `alembic upgrade head`).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
